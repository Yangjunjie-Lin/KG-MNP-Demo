"""Fail-closed lookups shared by lifecycle gates.

The lifecycle package stores JSON records for portability, but callers must
never be allowed to manufacture a valid-looking record by passing its IDs.
These helpers resolve IDs back to the registry and verify the minimum
identity/state closure before a gate can use an object.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .errors import LifecycleError
from .registry.manifest import load_manifest
from .store import list_records


def _required(value: Any, field: str, message: str = "required lifecycle reference") -> Any:
    if value in (None, "", [], {}):
        raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", f"{message}: {field}")
    return value


def record_by_id(root: Path, folder: str, field: str, identifier: str | None) -> dict[str, Any]:
    _required(identifier, field)
    for row in list_records(root, folder):
        if row.get(field) == identifier:
            if row.get("registry_id") != load_manifest(root).get("registry_id"):
                raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", f"cross-registry {field}")
            return row
    raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", f"{field} was not found")


def package_record(root: Path, package_id: str | None, *, status: str = "IMPORTED_VERIFIED") -> dict[str, Any]:
    row = record_by_id(root, "records/packages", "package_id", package_id)
    if row.get("import_status") != status or row.get("package_status") != "VALIDATED_UNPUBLISHED":
        raise LifecycleError("PACKAGE_IMPORT_INVALID", "package is not an imported verified package")
    storage = row.get("package_storage_ref")
    if not storage:
        raise LifecycleError("PACKAGE_IMPORT_INVALID", "package storage reference is missing")
    package_root = root / storage
    if not package_root.is_dir():
        raise LifecycleError("PACKAGE_IMPORT_INVALID", "package storage is missing")
    return row


def package_files(root: Path, record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], Path]:
    package_root = root / str(record["package_storage_ref"])
    manifest_path = package_root / "ontology-package.json"
    lock_path = package_root / "ontology-package.lock.json"
    if not manifest_path.is_file() or not lock_path.is_file():
        raise LifecycleError("PACKAGE_IMPORT_INVALID", "package manifest or lock is missing")
    try:
        manifest = json.loads(manifest_path.read_bytes())
        lock = json.loads(lock_path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError("PACKAGE_IMPORT_INVALID", "package manifest or lock is invalid") from exc
    if manifest.get("package_id") != record.get("package_id") or lock.get("package_id") != record.get("package_id"):
        raise LifecycleError("PACKAGE_IMPORT_INVALID", "package identity does not match record")
    return manifest, lock, package_root


def release_record(root: Path, release_id: str | None) -> dict[str, Any]:
    return record_by_id(root, "records/releases", "release_id", release_id)


def head(root: Path) -> dict[str, Any]:
    path = root / "state" / "registry-head.json"
    if not path.is_file():
        raise LifecycleError("LIFECYCLE_REGISTRY_INVALID", "registry head is missing")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", "registry head is invalid") from exc
    if not value.get("head_hash") or not value.get("content_digest"):
        raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", "registry head is incomplete")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def real_archive(root: Path, record: dict[str, Any]) -> Path:
    ref = record.get("archive_object_ref")
    if not ref:
        raise LifecycleError("PACKAGE_IMPORT_INVALID", "package archive reference is missing")
    path = root / ref
    if not path.is_file():
        raise LifecycleError("PACKAGE_IMPORT_INVALID", "package archive is missing")
    digest = file_sha256(path)
    if digest != record.get("archive_sha256"):
        raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", "package archive digest mismatch")
    return path


__all__ = ["file_sha256", "head", "package_files", "package_record", "real_archive", "record_by_id", "release_record"]
