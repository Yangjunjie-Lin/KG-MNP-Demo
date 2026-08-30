"""Cross-platform conservative operation lock and multi-directory commit."""

from __future__ import annotations

import json
import os
import secrets
import shutil
from pathlib import Path

from .errors import ArtifactTamperedError, WorkspaceOperationLockedError
from .security import fsync_directory


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

    def __enter__(self):
        if self.staging.exists():
            shutil.rmtree(self.staging)
        for name in self.mapping:
            (self.staging / name).mkdir(parents=True, exist_ok=False)
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
                source.replace(destination)
                fsync_directory(destination.parent)
                moved.append((source, destination))
        except BaseException:
            for _source, destination in reversed(moved):
                if destination.exists():
                    shutil.rmtree(destination)
            raise
        self.staging.rmdir()
        self._committed = True

    def __exit__(self, exc_type, exc, tb):
        if not self._committed and self.staging.exists():
            shutil.rmtree(self.staging)
