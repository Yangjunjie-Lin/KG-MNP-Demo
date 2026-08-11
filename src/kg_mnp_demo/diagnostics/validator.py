"""Structural and independent authority reconstruction validators."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from .contracts import strict_json_file, validate_diagnostic_contract
from .engine import AuthoritySnapshot, reconstruct_diagnostics
from .issue import validate_diagnostic_identity
from .package import canonical_issue_sort_key, diagnostic_package_semantic_content


def _mapping(value: Mapping[str, Any] | Path | str) -> dict[str, Any]:
    if isinstance(value, (Path, str)):
        return strict_json_file(Path(value))
    return dict(value)


def validate_diagnostic_package(
    package: Mapping[str, Any] | Path | str,
) -> dict[str, Any]:
    value = _mapping(package)
    validate_diagnostic_contract("diagnostic-package", value)
    validate_diagnostic_contract("diagnostic-manifest", value["manifest"])
    for issue in value["issues"]:
        validate_diagnostic_contract("diagnostic-issue", issue)
        validate_diagnostic_identity(issue)
    if value["issues"] != sorted(value["issues"], key=canonical_issue_sort_key):
        raise ValueError("diagnostic issue order is not canonical")
    manifest = value["manifest"]
    issue_ids = [issue["diagnostic_id"] for issue in value["issues"]]
    if manifest["issue_ids"] != issue_ids or manifest["issues_total"] != len(issue_ids):
        raise ValueError("diagnostic manifest issue inventory mismatch")
    digest = semantic_hash(diagnostic_package_semantic_content(value))
    if (
        manifest["package_semantic_hash"] != digest
        or manifest["package_id"] != f"urn:kg-mnp:diagnostic-package:{digest}"
    ):
        raise ValueError("diagnostic package identity mismatch")
    if manifest["diagnostic_policy_hash"] != value["authority_bindings"]["diagnostic_policy_hash"]:
        raise ValueError("diagnostic policy identity mismatch")
    return value


def validate_diagnostic_package_against_authorities(
    package: Mapping[str, Any] | Path | str,
    authorities: AuthoritySnapshot | Mapping[str, Any] | Path | str,
) -> dict[str, Any]:
    """Rebuild every issue; a self-consistent rehash cannot pass this gate."""

    actual = validate_diagnostic_package(package)
    authority_value: AuthoritySnapshot | Mapping[str, Any]
    if isinstance(authorities, (Path, str)):
        authority_value = strict_json_file(Path(authorities))
    else:
        authority_value = authorities
    expected = reconstruct_diagnostics(authority_value).to_dict()
    if canonical_json_bytes(actual) != canonical_json_bytes(expected):
        raise ValueError("diagnostic package does not reconstruct from authorities")
    return {
        "valid": True,
        "deterministic_reconstruction_match": True,
        "package_id": actual["manifest"]["package_id"],
        "package_semantic_hash": actual["manifest"]["package_semantic_hash"],
        "status": "DIAGNOSTICS_VALIDATED",
    }


validate_package_against_authorities = validate_diagnostic_package_against_authorities
