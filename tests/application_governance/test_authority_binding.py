from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.diagnostics.attestation import build_application_phase03_attestation
from kg_mnp_demo.diagnostics.engine import reconstruct_diagnostics
from kg_mnp_demo.governance.authority_binding import load_verified_phase03_authority
from kg_mnp_demo.governance.errors import GovernanceError, GovernanceErrorCode

from tests.diagnostics._helpers import bindings


def snapshot():
    value = bindings()
    focus = "urn:kg-mnp:phase04:test:missing"
    path = "urn:kg-mnp:phase04:test:property"
    return {
        "authority_bindings": value.to_dict(),
        "requirements": [
            {
                "focus_node": focus,
                "path": path,
                "requirement_type": "CONTROLLED_SHACL_MIN_COUNT",
                "authority_iri": "urn:kg-mnp:phase04:test:constraint",
                "shape_iri": "urn:kg-mnp:phase04:test:shape",
                "constraint_iri": "urn:kg-mnp:phase04:test:constraint",
                "module": "phase04-authority-test",
                "publication_id": value.publication_id,
                "min_count": 1,
                "max_count": 1,
            }
        ],
        "facts": [],
        "constraint_results": [],
        "candidates": [],
        "conflict_rules": [],
    }


def authority_documents():
    source = snapshot()
    package = reconstruct_diagnostics(source).to_dict()
    value = bindings()
    attestation = build_application_phase03_attestation(
        commit_sha="1" * 40,
        authority_bindings=value,
        package=package,
        repository_before_hash=value.repository_semantic_hash,
        repository_after_hash=value.repository_semantic_hash,
        controlled_scenarios_total=4,
        controlled_scenarios_passed=4,
        determinism_runs=2,
        determinism_passed=True,
        permutation_attacks=1,
        permutation_passed=True,
        authority_tamper_attempts=1,
        authority_tamper_blocked=1,
        missingness_attacks=1,
        missingness_expected_results=1,
        conflict_attacks=1,
        conflict_expected_results=1,
        evidence_attacks=1,
        evidence_expected_results=1,
        xss_attempts=1,
        xss_blocked=1,
        external_requests=0,
        direct_graphdb_attempts=1,
        direct_graphdb_blocked=1,
    )
    return source, package, attestation


def test_phase03_is_reconstructed_before_issues_are_exposed() -> None:
    source, package, attestation = authority_documents()
    authority = load_verified_phase03_authority(
        diagnostic_package=package,
        phase03_attestation=attestation,
        authority_snapshot=source,
    )
    issue = next(iter(authority.issues.values()))
    assert issue["classification"] == "REQUIRED_VALUE_MISSING"
    assert (
        authority.diagnostic_package_hash
        == package["manifest"]["package_semantic_hash"]
    )


def test_self_consistent_diagnostic_rehash_cannot_replace_phase03_authority() -> None:
    source, package, attestation = authority_documents()
    attacked = copy.deepcopy(package)
    attacked["issues"][0]["explanation"] = "forged and caller will rehash"
    with pytest.raises(GovernanceError) as caught:
        load_verified_phase03_authority(
            diagnostic_package=attacked,
            phase03_attestation=attestation,
            authority_snapshot=source,
        )
    assert caught.value.code == GovernanceErrorCode.AUTHORITY_MISMATCH


def test_wrong_publication_attestation_is_rejected() -> None:
    source, package, attestation = authority_documents()
    attacked = copy.deepcopy(attestation)
    attacked["publication_id"] = "urn:kg-mnp:e2e-publication:" + "9" * 64
    with pytest.raises(GovernanceError) as caught:
        load_verified_phase03_authority(
            diagnostic_package=package,
            phase03_attestation=attacked,
            authority_snapshot=source,
        )
    assert caught.value.code == GovernanceErrorCode.AUTHORITY_MISMATCH
