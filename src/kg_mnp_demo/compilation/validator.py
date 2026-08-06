"""Independent closed-set reconstruction validator for compiled artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .compiler import build_artifact_set
from .contracts import CompilationContractError, validate_compilation_contract
from ..modeling.dependencies import ROOT
from .manifest import compilation_manifest_hash


class CompilationValidationError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompilationValidationError(f"cannot read JSON artifact {path}: {exc}") from exc


def _relative_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def validate_compilation_package_against_authorities(
    compilation_directory: Path,
    cleaned_partial_data: Mapping[str, Any],
    proposal: Mapping[str, Any],
    final_review_decision_log: Mapping[str, Any],
    confirmed_modeling_package: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    terminology_profile: Mapping[str, Any],
    proposal_policy: Mapping[str, Any],
    review_policy: Mapping[str, Any],
    compiler_policy: Mapping[str, Any] | None = None,
    *,
    authority_root: Path = ROOT,
) -> dict[str, Any]:
    root = Path(compilation_directory)
    if not root.is_dir():
        raise CompilationValidationError(f"compilation directory is missing: {root}")
    try:
        expected_files, expected_manifest = build_artifact_set(
            cleaned_partial_data, proposal, final_review_decision_log,
            confirmed_modeling_package, ontology_baseline, mapping_rules,
            terminology_profile,
            proposal_policy,
            review_policy,
            compiler_policy,
            authority_root=authority_root,
        )
    except Exception as exc:
        raise CompilationValidationError(f"authoritative reconstruction failed: {exc}") from exc

    actual_manifest_path = root / "compilation-manifest.json"
    if not actual_manifest_path.is_file():
        raise CompilationValidationError("compilation-manifest.json is missing")
    actual_manifest = _load(actual_manifest_path)
    try:
        validate_compilation_contract("compilation-manifest", actual_manifest)
    except CompilationContractError as exc:
        raise CompilationValidationError(f"invalid compilation manifest contract: {exc}") from exc
    if compilation_manifest_hash(actual_manifest) != actual_manifest.get("compilation_semantic_hash"):
        raise CompilationValidationError("compilation manifest semantic self-hash mismatch")
    if actual_manifest.get("compilation_id") != expected_manifest.get("compilation_id"):
        raise CompilationValidationError("compilation_id does not match authoritative reconstruction")
    if actual_manifest.get("compilation_semantic_hash") != expected_manifest.get("compilation_semantic_hash"):
        raise CompilationValidationError("compilation manifest semantic hash mismatch")

    expected_paths = set(expected_files) | {"compilation-manifest.json"}
    actual_paths = _relative_files(root)
    extras = sorted(actual_paths - expected_paths)
    missing = sorted(expected_paths - actual_paths)
    if extras:
        raise CompilationValidationError("unexpected artifact(s): " + ", ".join(extras))
    if missing:
        raise CompilationValidationError("missing artifact(s): " + ", ".join(missing))

    for relative, expected_bytes in expected_files.items():
        actual_bytes = (root / relative).read_bytes()
        if actual_bytes != expected_bytes:
            raise CompilationValidationError(f"artifact bytes do not match authoritative reconstruction: {relative}")

    expected_records = {
        record["relative_path"]: record for record in expected_manifest["artifact_manifest"]
    }
    actual_records = {
        record.get("relative_path"): record
        for record in actual_manifest.get("artifact_manifest", [])
        if isinstance(record, Mapping)
    }
    if set(actual_records) != set(expected_records):
        raise CompilationValidationError("manifest artifact set does not match expected closed set")
    for relative, expected_record in expected_records.items():
        if actual_records[relative] != expected_record:
            raise CompilationValidationError(f"manifest artifact record mismatch: {relative}")

    return {
        "valid": True,
        "source_package_valid": True,
        "deterministic_reconstruction_match": True,
        "shacl_status": actual_manifest.get("shacl_status"),
        "owl_consistency_status": actual_manifest.get("owl_consistency_status"),
        "release_status": actual_manifest.get("release_status"),
        "compilation_id": actual_manifest.get("compilation_id"),
    }


def validate_compilation_package(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Short alias used by integrations and tests."""

    return validate_compilation_package_against_authorities(*args, **kwargs)
