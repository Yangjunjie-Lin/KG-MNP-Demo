"""Cross-platform atomic semantic build commit."""

from __future__ import annotations

import shutil
from pathlib import Path

from kg_mnp.ingestion.transaction import WorkspaceOperationLock

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
        self._lock = WorkspaceOperationLock(self.workspace, "semantic-compilation")

    def __enter__(self):
        self._lock.__enter__()
        if self.staging.exists():
            shutil.rmtree(self.staging)
        for name in self.destinations:
            (self.staging / name).mkdir(parents=True, exist_ok=False)
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
                source.replace(destination)
                moved.append(destination)
            self.staging.rmdir()
            self._committed = True
        except BaseException:
            for destination in reversed(moved):
                if destination.exists():
                    shutil.rmtree(destination)
            raise

    def __exit__(self, exc_type, exc, tb):
        if not self._committed and self.staging.exists():
            shutil.rmtree(self.staging)
        self._lock.__exit__(exc_type, exc, tb)
