"""Cross-platform atomic semantic build commit."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from zhigou_toolchain._path_security import _assert_components_are_local
from zhigou_toolchain.ingestion.security import fsync_directory
from zhigou_toolchain.ingestion.transaction import (
    WorkspaceOperationLock,
    commit_staged_directory,
)

from .errors import PackageError
from .identifiers import package_storage_key
from .packaging.verifier import verify_package


class SemanticCompilationTransaction:
    def __init__(self, workspace: Path | str, *, build_id: str, package_id: str) -> None:
        self.workspace = Path(workspace).resolve(strict=True)
        self.build_id = build_id
        self.package_id = package_id
        build_key = package_storage_key(build_id)
        self.staging = self.workspace / "tmp" / "compilation" / build_key
        self.destinations = {
            "build": self.workspace / "artifacts" / "builds" / "compilation" / build_key,
            "validation": self.workspace / "artifacts" / "validation" / "compilation" / build_key,
            "package": self.workspace / "artifacts" / "packages" / package_storage_key(package_id),
        }
        self._committed = False
        self._owned_staging = False
        self._lock = WorkspaceOperationLock(self.workspace, "semantic-compilation")

    def __enter__(self):
        self._lock.__enter__()
        try:
            parent = self.staging.parent
            _assert_components_are_local(parent, label="compilation staging root")
            parent.mkdir(parents=True, exist_ok=True)
            self.staging = Path(tempfile.mkdtemp(prefix=package_storage_key(self.build_id) + "-", dir=parent))
            self._owned_staging = True
            for name in self.destinations:
                (self.staging / name).mkdir(exist_ok=False)
        except BaseException:
            try:
                if self._owned_staging and self.staging.exists():
                    shutil.rmtree(self.staging)
            finally:
                self._lock.__exit__(None, None, None)
            raise
        return self

    def directory(self, role: str) -> Path:
        return self.staging / role

    def commit(self) -> None:
        package_destination = self.destinations["package"]
        if package_destination.exists():
            verify_package(package_destination)
            raise PackageError("valid immutable package already exists; caller must compare/reuse", code="ONTOLOGY_PACKAGE_CONFLICT")
        packages_root = package_destination.parent
        if packages_root.is_dir():
            import json

            staged_manifest = json.loads((self.directory("package") / "ontology-package.json").read_bytes())
            for candidate in packages_root.iterdir():
                manifest_path = candidate / "ontology-package.json"
                if not candidate.is_dir() or candidate.name == "exports" or not manifest_path.is_file():
                    continue
                manifest = json.loads(manifest_path.read_bytes())
                if manifest.get("package_name") == staged_manifest["package_name"] and manifest.get("package_version") == staged_manifest["package_version"] and manifest.get("package_id") != staged_manifest["package_id"]:
                    raise PackageError("same package name/version has different content", code="ONTOLOGY_PACKAGE_CONFLICT")
        existing = [path.exists() for path in self.destinations.values()]
        if any(existing):
            raise PackageError("partial or conflicting semantic build destinations exist", code="ONTOLOGY_PACKAGE_CONFLICT")
        moved = []
        try:
            for role, destination in self.destinations.items():
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = self.directory(role)
                commit_staged_directory(source, destination)
                moved.append(destination)
                fsync_directory(destination.parent)
            self.staging.rmdir()
            self._committed = True
        except BaseException:
            for destination in reversed(moved):
                if destination.exists():
                    shutil.rmtree(destination)
            raise

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._owned_staging and not self._committed and self.staging.exists():
                shutil.rmtree(self.staging)
        finally:
            self._lock.__exit__(exc_type, exc, tb)
