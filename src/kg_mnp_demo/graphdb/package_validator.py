from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..modeling.dependencies import ROOT
from ._io import read_json, safe_relative_path
from .package_builder import build_graphdb_import_package, GraphDBPackageError


class GraphDBPackageValidationError(ValueError):
    pass


def validate_graphdb_import_package(
    package_directory: Path,
    *,
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
    root: Path = ROOT,
) -> dict[str, Any]:
    package_directory = Path(package_directory).resolve()
    actual_manifest_path = package_directory / "graphdb-import-manifest.json"
    if not actual_manifest_path.is_file():
        raise GraphDBPackageValidationError("graphdb-import-manifest.json is missing")
    actual = read_json(actual_manifest_path)
    try:
        expected = build_graphdb_import_package(compilation_directory, cleaned_partial_data, proposal, final_review_decision_log, confirmed_modeling_package, ontology_baseline, mapping_rules, terminology_profile, proposal_policy, review_policy, compiler_policy, output_dir=None, root=root)
    except GraphDBPackageError as exc:
        raise GraphDBPackageValidationError(str(exc)) from exc
    expected_manifest = expected["manifest"]
    if actual != expected_manifest:
        raise GraphDBPackageValidationError("GraphDB import manifest does not match independent reconstruction")
    expected_paths = set(expected["files"])
    actual_paths = {path.relative_to(package_directory).as_posix() for path in package_directory.rglob("*") if path.is_file()}
    if actual_paths != expected_paths:
        raise GraphDBPackageValidationError("GraphDB package artifact closed set mismatch")
    for relative, data in expected["files"].items():
        safe_relative_path(relative)
        if (package_directory / relative).read_bytes() != data:
            raise GraphDBPackageValidationError(f"artifact bytes mismatch: {relative}")
    return {"valid": True, "source_package_valid": True, "deterministic_reconstruction_match": True, "shacl_status": "CONFORMS", "owl_consistency_status": "CONSISTENT", "release_status": "FORMALLY_VALIDATED", "publication_id": actual["publication_id"]}


validate_package = validate_graphdb_import_package
