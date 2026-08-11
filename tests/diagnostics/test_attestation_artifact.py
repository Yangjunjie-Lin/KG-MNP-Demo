from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.diagnostics import reconstruct_diagnostics
from kg_mnp_demo.diagnostics.artifact_verifier import (
    DiagnosticArtifactVerificationError,
    verify_application_phase03_artifact,
)
from kg_mnp_demo.diagnostics.attestation import build_application_phase03_attestation
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

from ._helpers import bindings, snapshot


def write_artifact(root):
    authority = bindings()
    package = reconstruct_diagnostics(snapshot())
    attestation = build_application_phase03_attestation(
        commit_sha="1" * 40,
        authority_bindings=authority,
        package=package,
        repository_before_hash=authority.repository_semantic_hash,
        repository_after_hash=authority.repository_semantic_hash,
        controlled_scenarios_total=4,
        controlled_scenarios_passed=4,
        determinism_runs=2,
        determinism_passed=True,
        permutation_attacks=5,
        permutation_passed=True,
        authority_tamper_attempts=4,
        authority_tamper_blocked=4,
        missingness_attacks=5,
        missingness_expected_results=5,
        conflict_attacks=5,
        conflict_expected_results=5,
        evidence_attacks=5,
        evidence_expected_results=5,
        xss_attempts=5,
        xss_blocked=5,
        external_requests=0,
        direct_graphdb_attempts=1,
        direct_graphdb_blocked=1,
    )
    documents = {
        "application-phase03-attestation.json": attestation,
        "diagnostics-summary.json": {
            "contract_version": "1.0",
            "diagnostic_package_hash": attestation["diagnostic_package_hash"],
            "issues_total": attestation["issues_total"],
            "issues_by_classification": attestation["issues_by_classification"],
            "requirements_evaluated": attestation["requirements_evaluated"],
            "constraints_evaluated": attestation["constraints_evaluated"],
            "status": "PASS",
        },
        "diagnostic-determinism.json": {
            "contract_version": "1.0",
            "diagnostic_package_hash": attestation["diagnostic_package_hash"],
            "determinism_runs": 2,
            "canonical_hashes": [attestation["diagnostic_package_hash"]] * 2,
            "determinism_passed": True,
            "permutation_attacks": 5,
            "permutation_passed": True,
            "status": "PASS",
        },
        "authority-binding.json": {
            "contract_version": "1.0",
            **authority.to_dict(),
            "status": "PASS",
        },
        "security-summary.json": {
            "contract_version": "1.0",
            **{
                key: attestation[key]
                for key in (
                    "authority_tamper_attempts",
                    "authority_tamper_blocked",
                    "missingness_attacks",
                    "missingness_expected_results",
                    "conflict_attacks",
                    "conflict_expected_results",
                    "evidence_attacks",
                    "evidence_expected_results",
                    "xss_attempts",
                    "xss_blocked",
                    "external_requests",
                    "direct_graphdb_attempts",
                    "direct_graphdb_blocked",
                )
            },
            "status": "PASS",
        },
    }
    root.mkdir()
    for name, value in documents.items():
        (root / name).write_bytes(canonical_json_bytes(value) + b"\n")
    return documents


def test_exact_artifact_is_verified_and_tampering_is_rejected(tmp_path) -> None:
    root = tmp_path / "artifact"
    documents = write_artifact(root)
    assert verify_application_phase03_artifact(root)["status"] == "APPLICATION_DIAGNOSTICS_VERIFIED"
    attacked = copy.deepcopy(documents["security-summary.json"])
    attacked["xss_blocked"] -= 1
    (root / "security-summary.json").write_bytes(canonical_json_bytes(attacked))
    with pytest.raises(DiagnosticArtifactVerificationError):
        verify_application_phase03_artifact(root)


def test_artifact_rejects_extra_files_duplicate_keys_and_paths(tmp_path) -> None:
    root = tmp_path / "artifact"
    write_artifact(root)
    (root / "unexpected.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DiagnosticArtifactVerificationError, match="closed set"):
        verify_application_phase03_artifact(root)
    (root / "unexpected.json").unlink()
    (root / "security-summary.json").write_text('{"status":"PASS","STATUS":"FAILED"}', encoding="utf-8")
    with pytest.raises(DiagnosticArtifactVerificationError, match="JSON"):
        verify_application_phase03_artifact(root)
