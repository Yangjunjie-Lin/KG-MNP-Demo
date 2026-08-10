"""Deterministic workbench package builder and validator."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.modeling.dependencies import ROOT

from .binding import WorkbenchBinding
from .contracts import strict_json_file, validate_workbench_contract
from .errors import WorkbenchError, WorkbenchErrorCode
from .policy import (
    ALLOWED_PHASE01_ROUTES,
    WORKBENCH_VERSION,
    load_workbench_policy,
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


def build_workbench_package(
    output_directory: Path,
    binding: WorkbenchBinding,
    *,
    source_directory: Path = ROOT / "web" / "workbench",
) -> dict[str, Any]:
    output = Path(output_directory)
    source = Path(source_directory)
    if output.exists() and (output.is_symlink() or not output.is_dir()):
        raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID)
    output.mkdir(parents=True, exist_ok=True)
    for child in sorted(output.rglob("*"), reverse=True):
        if child.is_symlink():
            raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID)
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    for name in FRONTEND_FILES:
        source_file = source / name
        target = output / name
        if source_file.is_symlink() or not source_file.is_file():
            raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, target)
    policy = load_workbench_policy()
    manifest = {
        "contract_version": "1.0",
        "workbench_version": WORKBENCH_VERSION,
        "frontend_build_hash": _frontend_hash(output),
        "phase01_attestation_hash": binding.phase01_attestation_hash,
        "publication_id": binding.publication_id,
        "publication_semantic_hash": binding.publication_semantic_hash,
        "repository_semantic_hash": binding.repository_semantic_hash,
        "query_registry_hash": binding.query_registry_hash,
        "runtime_policy_hash": workbench_policy_hash(policy),
        "allowed_routes": list(ALLOWED_PHASE01_ROUTES),
        "view_model_contract_hash": view_model_contract_hash(),
        "semantic_authority": False,
        "release_status": "WORKBENCH_PACKAGE_VALIDATED",
        "status": "WORKBENCH_PACKAGE_VALIDATED",
    }
    validate_workbench_contract("manifest", manifest)
    (output / "workbench-manifest.json").write_bytes(
        canonical_json_bytes(manifest) + b"\n"
    )
    validate_workbench_package(output, binding)
    return manifest


def validate_workbench_package(
    directory: Path,
    binding: WorkbenchBinding,
) -> dict[str, Any]:
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID)
    entries = [path for path in root.rglob("*") if path.is_file()]
    names = {path.relative_to(root).as_posix() for path in entries}
    if names != PACKAGE_FILES or any(path.is_symlink() for path in root.rglob("*")):
        raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID)
    try:
        manifest = strict_json_file(root / "workbench-manifest.json")
        validate_workbench_contract("manifest", manifest)
    except Exception as exc:
        raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID) from exc
    expected = {
        "frontend_build_hash": _frontend_hash(root),
        "phase01_attestation_hash": binding.phase01_attestation_hash,
        "publication_id": binding.publication_id,
        "publication_semantic_hash": binding.publication_semantic_hash,
        "repository_semantic_hash": binding.repository_semantic_hash,
        "query_registry_hash": binding.query_registry_hash,
        "runtime_policy_hash": workbench_policy_hash(),
        "allowed_routes": list(ALLOWED_PHASE01_ROUTES),
        "view_model_contract_hash": view_model_contract_hash(),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID)
    for name in FRONTEND_FILES:
        lowered = (root / name).read_bytes().lower()
        if any(marker in lowered for marker in FORBIDDEN_BUNDLE_MARKERS):
            raise WorkbenchError(WorkbenchErrorCode.PACKAGE_INVALID)
    return manifest
