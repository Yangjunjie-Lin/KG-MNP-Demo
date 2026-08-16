"""Cross-process locked, atomic persistence for registry and current pointer."""

from __future__ import annotations

import hashlib
import os
import tempfile
import threading
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any, BinaryIO, Self, TypeVar

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

from .contracts import strict_json_bytes
from .errors import ActivationError, ActivationErrorCode
from .registry import ActivationRegistry
from .security import freeze_state_directory
from .validator import validate_activation_registry_against_authorities

T = TypeVar("T")

_THREAD_LOCKS_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.RLock] = {}


def _thread_lock(path: Path) -> threading.RLock:
    key = os.path.normcase(str(path))
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


def _link_like(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        return bool(is_junction is not None and is_junction())
    except OSError:
        return True


def _freeze_store_directory(path: Path) -> Path:
    """Reject link-like lexical components before creating/resolving the root."""

    requested = Path(path)
    absolute = Path(os.path.abspath(os.fspath(requested)))
    try:
        for candidate in (*reversed(absolute.parents), absolute):
            if candidate.exists() and _link_like(candidate):
                raise ActivationError(ActivationErrorCode.PATH_REJECTED)
    except ActivationError:
        raise
    except OSError as exc:
        raise ActivationError(ActivationErrorCode.PATH_REJECTED) from exc
    return freeze_state_directory(requested)


class _ProcessFileLock:
    """One-byte advisory lock using only the Python standard library."""

    def __init__(self, path: Path):
        self.path = path
        self.stream: BinaryIO | None = None

    def __enter__(self) -> Self:
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(self.path, flags, 0o600)
            self.stream = os.fdopen(descriptor, "r+b", buffering=0)
            self.stream.seek(0, os.SEEK_END)
            if self.stream.tell() == 0:
                self.stream.write(b"\0")
                self.stream.flush()
                os.fsync(self.stream.fileno())
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX)
        except OSError as exc:
            if self.stream is not None:
                self.stream.close()
                self.stream = None
            raise ActivationError(
                ActivationErrorCode.ACTIVATION_CONCURRENCY_CONFLICT,
                "could not acquire activation process lock",
            ) from exc
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self.stream is None:
            return
        try:
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        finally:
            self.stream.close()
            self.stream = None


class ActivationStateStore:
    """Startup-frozen store for one registry/current-pointer pair.

    A small write-ahead transaction makes a process crash between the two
    atomic replacements detectable and deterministically recoverable.  Read-only
    callers deliberately do not recover; they fail closed instead.
    """

    def __init__(
        self,
        state_directory: Path,
        authority_supplier: Callable[[], object] | object,
    ):
        self.directory = _freeze_store_directory(Path(state_directory))
        self.registry_path = self.directory / "activation-registry.json"
        self.pointer_path = self.directory / "current-publication-pointer.json"
        self.lock_path = self.directory / "activation.lock"
        self.transaction_path = self.directory / "transaction.json"
        self._resolved_parent = self.directory.resolve(strict=True)
        self._thread_lock = _thread_lock(self.lock_path)
        self._authority_supplier = authority_supplier

    def _authority(self) -> object:
        value = (
            self._authority_supplier()
            if callable(self._authority_supplier)
            else self._authority_supplier
        )
        if value is None:
            raise ActivationError(ActivationErrorCode.AUTHORITY_MISMATCH)
        return value

    def _assert_paths_safe(self) -> None:
        try:
            if self.directory.resolve(
                strict=True
            ) != self._resolved_parent or _link_like(self.directory):
                raise ActivationError(ActivationErrorCode.PATH_REJECTED)
            for path in (
                self.registry_path,
                self.pointer_path,
                self.lock_path,
                self.transaction_path,
            ):
                if path.exists() and _link_like(path):
                    raise ActivationError(ActivationErrorCode.PATH_REJECTED)
        except ActivationError:
            raise
        except OSError as exc:
            raise ActivationError(ActivationErrorCode.PATH_REJECTED) from exc

    @contextmanager
    def _locked(self):
        with self._thread_lock:
            self._assert_paths_safe()
            with _ProcessFileLock(self.lock_path):
                self._assert_paths_safe()
                yield

    def initialize(
        self, *, observed_at: str | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        with self._locked():
            if self.transaction_path.exists():
                self._recover_locked()
            if self.registry_path.exists() or self.pointer_path.exists():
                raise ActivationError(ActivationErrorCode.REPLAY_DETECTED)
            workspace = ActivationRegistry.initialize(
                self._authority(), observed_at=observed_at
            )
            self._commit_locked(workspace.value, workspace.current_pointer)
            return (
                _copy(workspace.value),
                _copy(workspace.current_pointer),
            )

    def load(
        self,
        *,
        expected_registry_hash: str | None = None,
        expected_head_event_hash: str | None = None,
        recover: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        with self._locked():
            if self.transaction_path.exists():
                if not recover:
                    raise ActivationError(
                        ActivationErrorCode.POINTER_TAMPERED,
                        "activation transaction is incomplete; read-only access is not ready",
                    )
                self._recover_locked()
            return self._load_locked(
                expected_registry_hash=expected_registry_hash,
                expected_head_event_hash=expected_head_event_hash,
            )

    def mutate(
        self,
        operation: Callable[[ActivationRegistry], T],
        *,
        expected_registry_hash: str | None = None,
        expected_head_event_hash: str | None = None,
    ) -> T:
        """Run a complete read/validate/mutate/commit under one process lock."""

        with self._locked():
            if self.transaction_path.exists():
                self._recover_locked()
            registry, pointer, _state = self._load_locked(
                expected_registry_hash=expected_registry_hash,
                expected_head_event_hash=expected_head_event_hash,
            )
            workspace = ActivationRegistry(registry, self._authority(), pointer)
            result = operation(workspace)
            workspace.reconstruct()
            self._commit_locked(workspace.value, workspace.current_pointer)
            return result

    def inspect(
        self,
        operation: Callable[[ActivationRegistry, Mapping[str, Any]], T],
        *,
        expected_registry_hash: str | None = None,
        expected_head_event_hash: str | None = None,
    ) -> T:
        """Run a read-only operation against one locked, validated snapshot.

        In particular this method never recovers an incomplete transaction and
        never persists a registry or pointer, which keeps resolver semantics
        strictly fail-closed.
        """

        with self._locked():
            if self.transaction_path.exists():
                raise ActivationError(
                    ActivationErrorCode.POINTER_TAMPERED,
                    "activation transaction is incomplete; current target is not ready",
                )
            registry, pointer, state = self._load_locked(
                expected_registry_hash=expected_registry_hash,
                expected_head_event_hash=expected_head_event_hash,
            )
            workspace = ActivationRegistry(registry, self._authority(), pointer)
            return operation(workspace, state)

    def _load_locked(
        self,
        *,
        expected_registry_hash: str | None = None,
        expected_head_event_hash: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        self._assert_paths_safe()
        if not self.registry_path.is_file() or not self.pointer_path.is_file():
            raise ActivationError(
                ActivationErrorCode.POINTER_TAMPERED,
                "registry and current pointer must both exist",
            )
        try:
            registry = _json_object(self.registry_path.read_bytes())
            pointer = _json_object(self.pointer_path.read_bytes())
        except ActivationError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise ActivationError(
                ActivationErrorCode.POINTER_TAMPERED,
                "activation state cannot be read as strict JSON",
            ) from exc
        state = validate_activation_registry_against_authorities(
            registry,
            self._authority(),
            current_pointer=pointer,
            expected_registry_hash=expected_registry_hash,
            expected_head_event_hash=expected_head_event_hash,
        )
        return registry, pointer, state

    def _commit_locked(
        self, registry: Mapping[str, Any], pointer: Mapping[str, Any]
    ) -> None:
        self._assert_paths_safe()
        registry_bytes = canonical_json_bytes(registry) + b"\n"
        pointer_bytes = canonical_json_bytes(pointer) + b"\n"
        transaction = {
            "contract_version": "1.0",
            "registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
            "pointer_sha256": hashlib.sha256(pointer_bytes).hexdigest(),
            "registry": dict(registry),
            "pointer": dict(pointer),
            "status": "PREPARED",
        }
        _atomic_write(self.transaction_path, canonical_json_bytes(transaction) + b"\n")
        _atomic_write(self.registry_path, registry_bytes)
        _atomic_write(self.pointer_path, pointer_bytes)
        self._remove_transaction()

    def _recover_locked(self) -> None:
        """Finish exactly the prepared transaction; never invent new state."""

        self._assert_paths_safe()
        try:
            transaction = _json_object(self.transaction_path.read_bytes())
            if (
                set(transaction)
                != {
                    "contract_version",
                    "registry_sha256",
                    "pointer_sha256",
                    "registry",
                    "pointer",
                    "status",
                }
                or transaction["contract_version"] != "1.0"
                or transaction["status"] != "PREPARED"
            ):
                raise ValueError("invalid transaction")
            registry_bytes = canonical_json_bytes(transaction["registry"]) + b"\n"
            pointer_bytes = canonical_json_bytes(transaction["pointer"]) + b"\n"
            if (
                hashlib.sha256(registry_bytes).hexdigest()
                != transaction["registry_sha256"]
                or hashlib.sha256(pointer_bytes).hexdigest()
                != transaction["pointer_sha256"]
            ):
                raise ValueError("transaction digest mismatch")
            validate_activation_registry_against_authorities(
                transaction["registry"],
                self._authority(),
                current_pointer=transaction["pointer"],
            )
        except ActivationError:
            raise
        except Exception as exc:
            raise ActivationError(
                ActivationErrorCode.POINTER_TAMPERED,
                "prepared activation transaction is invalid",
            ) from exc
        _atomic_write(self.registry_path, registry_bytes)
        _atomic_write(self.pointer_path, pointer_bytes)
        self._remove_transaction()

    def _remove_transaction(self) -> None:
        try:
            self.transaction_path.unlink(missing_ok=True)
            _fsync_directory(self.directory)
        except OSError as exc:
            raise ActivationError(
                ActivationErrorCode.POINTER_TAMPERED,
                "activation transaction commit marker could not be cleared",
            ) from exc


def _copy(value: Mapping[str, Any]) -> dict[str, Any]:
    return _json_object(canonical_json_bytes(value))


def _json_object(raw: bytes) -> dict[str, Any]:
    value = strict_json_bytes(raw)
    if not isinstance(value, dict):
        raise TypeError("JSON root must be an object")
    return value


def _atomic_write(path: Path, data: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        try:
            os.fchmod(descriptor, 0o600)
        except (AttributeError, OSError):
            pass
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except OSError as exc:
        raise ActivationError(
            ActivationErrorCode.POINTER_TAMPERED,
            f"atomic activation state persistence failed: {path.name}",
        ) from exc
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def _fsync_directory(directory: Path) -> None:
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            # Windows and some network filesystems do not expose directory fsync.
            pass
    finally:
        os.close(descriptor)
