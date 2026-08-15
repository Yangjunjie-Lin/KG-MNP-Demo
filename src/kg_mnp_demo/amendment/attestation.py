"""Deterministic Phase 05 attestation projection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from .contracts import validate_amendment_contract


def build_phase05_attestation(
    *,
    commit_sha: str,
    upstream_phase04_attestation_sha256: str,
    upstream_phase04_workspace_hash: str,
    production_pending_amendments: int,
    production_reentry_cycles: int = 0,
    production_new_publications: int = 0,
    controlled_fixture_hash: str,
    controlled_reentry_cycles: int,
    controlled_republication_cycles: int,
    security: Mapping[str, int],
    determinism_runs: int,
    determinism_passed: int,
    hashes: Mapping[str, str],
    diagnostics: Mapping[str, Any],
    status: str = "APPLICATION_AMENDMENT_REPUBLICATION_VERIFIED",
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "contract_version": "1.0",
        "commit_sha": commit_sha,
        "upstream_phase04_attestation_sha256": upstream_phase04_attestation_sha256,
        "upstream_phase04_workspace_hash": upstream_phase04_workspace_hash,
        "production_pending_amendments": production_pending_amendments,
        "production_reentry_cycles": production_reentry_cycles,
        "production_new_publications": production_new_publications,
        "controlled_fixture_hash": controlled_fixture_hash,
        "controlled_reentry_cycles": controlled_reentry_cycles,
        "controlled_republication_cycles": controlled_republication_cycles,
        **dict(security),
        "determinism_runs": determinism_runs,
        "determinism_passed": determinism_passed,
        **dict(hashes),
        "target_diagnostic_before": diagnostics.get("before"),
        "target_diagnostic_after": diagnostics.get("after"),
        "status": status,
    }
    validate_amendment_contract("application-phase05-attestation", value)
    return value


def attestation_hash(attestation: Mapping[str, Any]) -> str:
    return semantic_hash(attestation)


def deterministic_attestation_bytes(attestation: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(attestation) + b"\n"
