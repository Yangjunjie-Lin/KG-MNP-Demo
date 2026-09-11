"""Cross-platform conservative operation lock and multi-directory commit."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import tempfile
import time
from pathlib import Path

from zhigou_toolchain._path_security import _assert_components_are_local, _is_link_like

from .errors import ArtifactTamperedError, WorkspaceOperationLockedError
from .security import fsync_directory


def commit_staged_directory(staging: Path, destination: Path) -> None:
    """Publish a fresh directory while its caller holds the Workspace lock.

    Only transient Windows sharing denials are retried. Never delete a target
    that appeared concurrently, and never reinterpret a permanent denial as
    success. This is a filesystem step, not a Job fencing/CAS authority.
    """
    for attempt in range(6):
        _assert_components_are_local(staging, label="artifact staging")
        _assert_components_are_local(destination, label="artifact destination")
        if destination.exists():
            raise FileExistsError("artifact destination already exists")
        try:
            staging.rename(destination)
            return
        except PermissionError as exc:
            if (getattr(exc, "winerror", None) not in {5, 32, 33}
                    or attempt == 5 or destination.exists()
                    or _is_link_like(destination) or not staging.is_dir()):
                raise
            time.sleep(min(0.05 * (2 ** attempt), 0.2))


class WorkspaceOperationLock:
    def __init__(self, workspace: Path, operation: str = "ingestion") -> None:
        self.workspace = workspace.resolve(strict=True)
        self.operation = operation
        self.path = self.workspace / "tmp" / "locks" / f"{operation}.lock"
        self._held = False
        self._nonce = secrets.token_hex(16)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"pid": os.getpid(), "operation": self.operation, "nonce": self._nonce},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise WorkspaceOperationLockedError(
                f"workspace operation lock exists: {self.path.name}; inspect and remove only after proving the owner is inactive"
            ) from exc
        try:
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self._held = True
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._held:
            try:
                current = json.loads(self.path.read_bytes())
            except (OSError, UnicodeError, json.JSONDecodeError):
                current = None
            if current == {
                "nonce": self._nonce,
                "operation": self.operation,
                "pid": os.getpid(),
            }:
                self.path.unlink(missing_ok=True)
            self._held = False


class IngestionTransaction:
    def __init__(self, workspace: Path, run_hash: str) -> None:
        self.workspace = workspace.resolve(strict=True)
        self.run_hash = run_hash
        self.staging = self.workspace / "tmp" / "ingestion" / run_hash
        self.mapping = {
            "build": self.workspace / "artifacts" / "builds" / "ingestion" / run_hash,
            "evidence": self.workspace / "artifacts" / "evidence" / run_hash,
            "ir": self.workspace / "artifacts" / "ir" / run_hash,
            "validation": self.workspace / "artifacts" / "validation" / "ingestion" / run_hash,
        }
        self._committed = False
        self._owned_staging = False

    def __enter__(self):
        parent = self.staging.parent
        _assert_components_are_local(parent, label="ingestion staging root")
        parent.mkdir(parents=True, exist_ok=True)
        self.staging = Path(tempfile.mkdtemp(prefix=self.run_hash + "-", dir=parent))
        self._owned_staging = True
        try:
            for name in self.mapping:
                (self.staging / name).mkdir(exist_ok=False)
        except BaseException:
            shutil.rmtree(self.staging)
            raise
        return self

    def directory(self, name: str) -> Path:
        return self.staging / name

    def commit(self) -> None:
        existing = [path.exists() for path in self.mapping.values()]
        if any(existing):
            if all(existing):
                raise ArtifactTamperedError("run already exists; caller must verify before reuse")
            raise ArtifactTamperedError("partial formal run directories already exist")
        moved: list[tuple[Path, Path]] = []
        try:
            for name, destination in self.mapping.items():
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = self.staging / name
                commit_staged_directory(source, destination)
                moved.append((source, destination))
                fsync_directory(destination.parent)
        except BaseException:
            for _source, destination in reversed(moved):
                if destination.exists():
                    shutil.rmtree(destination)
            raise
        self.staging.rmdir()
        self._committed = True

    def __exit__(self, exc_type, exc, tb):
        if self._owned_staging and not self._committed and self.staging.exists():
            shutil.rmtree(self.staging)
