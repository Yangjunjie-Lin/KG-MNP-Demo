"""Deterministic identifiers, verification, and transactional artifact writes."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from zhigou_toolchain._path_security import (
    _assert_components_are_local,
    _is_link_like,
    validated_directory,
)
from zhigou_toolchain.contracts.canonical import bytes_sha256, semantic_hash, stable_urn
from zhigou_toolchain.contracts.document_io import deterministic_json_bytes
from zhigou_toolchain.ingestion.transaction import (
    WorkspaceOperationLock,
    commit_staged_directory,
)

from .errors import ModelingControlError, StaleModelingArtifactError
from .security import assert_safe_json, validate_safe_relative_path


def finalize_document(value: dict[str, Any], *, id_field: str, urn_kind: str) -> dict[str, Any]:
    document = copy.deepcopy(value)
    document.pop(id_field, None)
    document.pop("content_digest", None)
    assert_safe_json(document)
    content_digest = semantic_hash(document)
    document["content_digest"] = content_digest
    document[id_field] = stable_urn(urn_kind, {"content_digest": content_digest})
    return document


def verify_document(value: dict[str, Any], *, id_field: str, urn_kind: str) -> None:
    expected = finalize_document(value, id_field=id_field, urn_kind=urn_kind)
    if expected != value:
        raise StaleModelingArtifactError(f"{id_field} or content_digest mismatch")


def deterministic_id(kind: str, semantic_value: Any) -> str:
    assert_safe_json(semantic_value)
    return stable_urn(kind, semantic_value)


def artifact_manifest(files: dict[str, bytes]) -> dict[str, Any]:
    rows = [
        {"path": path, "sha256": bytes_sha256(content), "size_bytes": len(content)}
        for path, content in sorted(files.items())
    ]
    core = {"manifest_kind": "KG_MNP_MODELING_ARTIFACT_MANIFEST", "schema_version": "1.0.0", "artifacts": rows}
    digest_value = semantic_hash(core)
    return {**core, "content_digest": digest_value, "manifest_id": stable_urn("modeling-artifact-manifest", {"content_digest": digest_value})}


def transactional_write_directory(
    workspace: Path | str,
    *,
    operation: str,
    relative_destination: str,
    documents: dict[str, Any],
) -> Path:
    files = {name: deterministic_json_bytes(value) for name, value in documents.items()}
    return transactional_write_files(
        workspace,
        operation=operation,
        relative_destination=relative_destination,
        files=files,
    )


def transactional_write_files(
    workspace: Path | str,
    *,
    operation: str,
    relative_destination: str,
    files: dict[str, bytes],
) -> Path:
    validate_safe_relative_path(relative_destination)
    root = validated_directory(Path(workspace), label="modeling workspace")
    destination = root / relative_destination
    _assert_components_are_local(destination, label="modeling artifact destination")
    if root not in destination.parents:
        raise ModelingControlError("artifact destination escapes workspace")
    relative_parts = destination.relative_to(root).parts
    if relative_parts[:2] == ("artifacts", "packages") or relative_parts[:1] == ("registry",):
        raise ModelingControlError("modeling control plane cannot write packages or registry")
    for name in files:
        validate_safe_relative_path(name)
        if "/" in name or "\\" in name:
            raise ModelingControlError("artifact files must be direct children of their artifact set")
    files = dict(files)
    files["artifact-manifest.json"] = deterministic_json_bytes(artifact_manifest(files))
    with WorkspaceOperationLock(root, operation):
        if destination.exists():
            if not destination.is_dir() or destination.is_symlink():
                raise ModelingControlError("existing artifact destination is not a safe directory")
            entries = list(destination.iterdir())
            if any(_is_link_like(item) or not item.is_file() for item in entries):
                raise ModelingControlError("immutable artifact directory contains unlisted or unsafe entries")
            actual = {item.name: item.read_bytes() for item in entries}
            if actual != files:
                raise ModelingControlError("immutable artifact directory already exists with different bytes")
            return destination
        staging_root = root / "tmp" / "modeling" / operation
        _assert_components_are_local(staging_root, label="modeling staging root")
        staging_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=destination.name + "-", dir=staging_root))
        try:
            for name, content in files.items():
                (staging / name).write_bytes(content)
            destination.parent.mkdir(parents=True, exist_ok=True)
            commit_staged_directory(staging, destination)
        except BaseException:
            if staging.exists():
                shutil.rmtree(staging)
            raise
    return destination


def read_json(
    path: Path | str,
    *,
    max_bytes: int = 4 * 1024 * 1024,
    enforce_safe_json: bool = True,
) -> dict[str, Any]:
    source = Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > max_bytes:
        raise ModelingControlError("unsafe or oversized JSON artifact")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelingControlError(f"cannot read JSON artifact: {exc}") from exc
    if not isinstance(value, dict):
        raise ModelingControlError("artifact root must be an object")
    if enforce_safe_json:
        assert_safe_json(value, max_bytes=max_bytes)
    return value
