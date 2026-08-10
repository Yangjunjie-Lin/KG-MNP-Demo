from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.workbench.artifact_verifier import (
    WorkbenchArtifactVerificationError,
    verify_application_phase02_artifact,
)
from kg_mnp_demo.workbench.attestation import build_workbench_attestation
from kg_mnp_demo.workbench.binding import WorkbenchBinding

from ._helpers import PUBLICATION_HASH, PUBLICATION_ID, REPOSITORY_HASH, write_phase01_artifact


def write_artifact(directory, tmp_path):
    binding = WorkbenchBinding.load(write_phase01_artifact(tmp_path / "phase01"))
    browser = {
        "status": "PASS",
        "browser_name": "chromium",
        "browser_version": "131.0.6778.33",
        "browser_revision": "1148",
        "golden_scenario_count": 4,
        "golden_scenario_passed": 4,
        "external_requests": [],
        "service_worker_count": 0,
        "local_storage_entry_count": 0,
        "indexed_db_count": 0,
    }
    security = {
        "contract_version": "1.0",
        "xss_attack_count": 11,
        "xss_attack_blocked": 11,
        "relay_attack_count": 18,
        "relay_attack_blocked": 18,
        "authority_tamper_attack_count": 6,
        "authority_tamper_attack_blocked": 6,
        "direct_graphdb_access_attempt_count": 1,
        "direct_graphdb_access_blocked_count": 1,
        "status": "PASS",
    }
    attestation = build_workbench_attestation(
        commit_sha="1" * 40,
        binding=binding,
        frontend_build_hash="2" * 64,
        runtime_policy_hash="3" * 64,
        repository_hash_before=REPOSITORY_HASH,
        repository_hash_after=REPOSITORY_HASH,
        browser=browser,
        security=security,
        result_fidelity_status="PASS",
        traceability_view_status="PASS",
    )
    documents = {
        "application-phase02-attestation.json": attestation,
        "browser-smoke.json": {**browser, "javascript_errors": []},
        "security-summary.json": security,
        "binding-summary.json": {
            "contract_version": "1.0",
            "phase01_attestation_hash": binding.phase01_attestation_hash,
            "phase01_attestation_status": "APPLICATION_READONLY_VERIFIED",
            "publication_id": PUBLICATION_ID,
            "publication_semantic_hash": PUBLICATION_HASH,
            "repository_semantic_hash": REPOSITORY_HASH,
            "query_registry_hash": binding.query_registry_hash,
            "status": "PASS",
        },
        "graphdb-before-after.json": {
            "contract_version": "1.0",
            "expected": REPOSITORY_HASH,
            "before": REPOSITORY_HASH,
            "after": REPOSITORY_HASH,
            "repository_unchanged": True,
            "status": "PASS",
        },
    }
    directory.mkdir(parents=True)
    for name, value in documents.items():
        (directory / name).write_bytes(canonical_json_bytes(value) + b"\n")
    return documents


def test_closed_artifact_is_independently_verified(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    write_artifact(artifact, tmp_path)
    result = verify_application_phase02_artifact(artifact)
    assert result["status"] == "APPLICATION_WORKBENCH_VERIFIED"


@pytest.mark.parametrize(
    ("name", "field", "value"),
    [
        ("application-phase02-attestation.json", "repository_hash_after", "0" * 64),
        ("browser-smoke.json", "service_worker_count", 1),
        ("security-summary.json", "xss_attack_blocked", 10),
        ("binding-summary.json", "query_registry_hash", "0" * 64),
        ("graphdb-before-after.json", "repository_unchanged", False),
    ],
)
def test_artifact_tampering_fails_closed(tmp_path, name, field, value) -> None:
    artifact = tmp_path / "artifact"
    documents = write_artifact(artifact, tmp_path)
    attacked = copy.deepcopy(documents[name])
    attacked[field] = value
    (artifact / name).write_bytes(canonical_json_bytes(attacked) + b"\n")
    with pytest.raises(WorkbenchArtifactVerificationError):
        verify_application_phase02_artifact(artifact)


def test_artifact_rejects_unexpected_files_duplicate_keys_and_sensitive_data(tmp_path) -> None:
    artifact = tmp_path / "artifact"
    write_artifact(artifact, tmp_path)
    (artifact / "unexpected.json").write_text("{}", encoding="utf-8")
    with pytest.raises(WorkbenchArtifactVerificationError, match="closed set"):
        verify_application_phase02_artifact(artifact)
    (artifact / "unexpected.json").unlink()
    (artifact / "security-summary.json").write_text(
        '{"status":"PASS","STATUS":"FAILED"}',
        encoding="utf-8",
    )
    with pytest.raises(WorkbenchArtifactVerificationError, match="JSON"):
        verify_application_phase02_artifact(artifact)
