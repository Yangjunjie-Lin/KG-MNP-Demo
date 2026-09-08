"""Read-only manifest reconstruction for historical workbench artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from kg_mnp._path_security import closed_regular_files, validated_directory
from kg_mnp.modeling.canonical_json import canonical_json_bytes
from kg_mnp.modeling.dependencies import ROOT

from .binding import WorkbenchBinding
from .contracts import strict_json_file, validate_workbench_contract
from .errors import WorkbenchError, WorkbenchErrorCode
from .policy import (
    ALLOWED_PHASE01_ROUTES,
    WORKBENCH_VERSION,
    workbench_policy_hash,
)

FRONTEND_FILES = (
    "index.html",
    "assets/app.js",
    "assets/styles.css",
)
PACKAGE_FILES = frozenset((*FRONTEND_FILES, "workbench-manifest.json"))
FORBIDDEN_BUNDLE_MARKERS = (
    b"/repositories/",
    b"sparql endpoint",
    b"graph store protocol",
    b"graphdb username",
    b"graphdb password",
    b"graphdb license",
    b"0.0.0.0",
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _frontend_hash(directory: Path) -> str:
    entries = []
    for name in FRONTEND_FILES:
        raw = (directory / name).read_bytes()
        entries.append({"path": name, "sha256": _sha256(raw)})
    return _sha256(canonical_json_bytes(entries))


def view_model_contract_hash(root: Path = ROOT) -> str:
    entries = []
    for name in (
        "entity_view_model.schema.json",
        "fact_trace_view_model.schema.json",
    ):
        raw = (Path(root) / "schemas" / "workbench" / name).read_bytes()
        entries.append({"path": name, "sha256": _sha256(raw)})
    return _sha256(canonical_json_bytes(entries))


def reconstruct_workbench_manifest(
    source_directory: Path,
    binding: WorkbenchBinding,
) -> dict[str, Any]:
    source = validated_directory(source_directory, label="historical workbench source")
    if not set(FRONTEND_FILES) <= set(closed_regular_files(source, label="historical workbench")):
        raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID)
    manifest = {
        "contract_version": "1.0",
        "workbench_version": WORKBENCH_VERSION,
        "frontend_build_hash": _frontend_hash(source),
        "phase01_attestation_hash": binding.phase01_attestation_hash,
        "publication_id": binding.publication_id,
        "publication_semantic_hash": binding.publication_semantic_hash,
        "repository_semantic_hash": binding.repository_semantic_hash,
        "query_registry_hash": binding.query_registry_hash,
        "runtime_policy_hash": workbench_policy_hash(),
        "allowed_routes": list(ALLOWED_PHASE01_ROUTES),
        "view_model_contract_hash": view_model_contract_hash(),
        "semantic_authority": False,
        "release_status": "WORKBENCH_PACKAGE_VALIDATED",
        "status": "WORKBENCH_PACKAGE_VALIDATED",
    }
    validate_workbench_contract("manifest", manifest)
    return manifest


def validate_workbench_package(
    directory: Path,
    binding: WorkbenchBinding,
) -> dict[str, Any]:
    try:
        root = validated_directory(directory, label="historical workbench package")
        if set(closed_regular_files(root, label="historical workbench package")) != PACKAGE_FILES:
            raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID)
        manifest = strict_json_file(root / "workbench-manifest.json")
        validate_workbench_contract("manifest", manifest)
        expected = reconstruct_workbench_manifest(root, binding)
    except Exception as exc:
        raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID) from exc
    if manifest != expected:
        raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID)
    for name in FRONTEND_FILES:
        lowered = (root / name).read_bytes().lower()
        if any(marker in lowered for marker in FORBIDDEN_BUNDLE_MARKERS):
            raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID)
    return manifest
