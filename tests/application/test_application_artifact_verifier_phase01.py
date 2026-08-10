from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from kg_mnp_demo.application.artifact_verifier import (
    ArtifactVerificationError,
    verify_application_phase01_artifact,
)
from kg_mnp_demo.application.attestation import build_application_attestation
from kg_mnp_demo.application.query_registry import QueryRegistry

from ._phase01_helpers import synthetic_binding


def _write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _artifact(directory: Path) -> dict[str, dict]:
    binding = synthetic_binding()
    registry = QueryRegistry.load()
    graph_hash = binding.graphdb_semantic_hash
    attestation = build_application_attestation(
        binding=binding,
        registry=registry,
        live_graphdb_semantic_hash_before=graph_hash,
        live_graphdb_semantic_hash_after=graph_hash,
        golden_query_count=12,
        golden_query_passed=12,
        mutation_attack_count=15,
        mutation_attack_blocked=15,
        live_repository_tamper_attack_count=3,
        live_repository_tamper_attack_blocked=3,
        traceability_checks={
            "fact_level": "PASS",
            "review": "PASS",
            "evidence": "PASS",
            "source": "PASS",
            "publication_lineage": "PASS",
        },
        http_runtime={
            "bind_host": "127.0.0.1",
            "read_only": True,
            "golden_http_status": "PASS",
        },
        result_determinism="PASS",
    )
    authority = attestation["publication_authority_reconstruction"]
    documents = {
        "application-attestation.json": attestation,
        "query-registry-manifest.json": registry.manifest(),
        "golden-query-summary.json": {
            "contract_version": "1.0",
            "publication_id": binding.publication_id,
            "query_registry_hash": registry.document_hash,
            "golden_query_count": 12,
            "golden_query_passed": 12,
            "status": "PASS",
        },
        "security-summary.json": {
            "contract_version": "1.0",
            "publication_id": binding.publication_id,
            "repository_id": binding.repository_id,
            "mutation_attack_count": 15,
            "mutation_attack_blocked": 15,
            "live_repository_tamper_attack_count": 3,
            "live_repository_tamper_attack_blocked": 3,
            "status": "PASS",
        },
        "graphdb-before-after.json": {
            "contract_version": "1.0",
            "publication_id": binding.publication_id,
            "repository_id": binding.repository_id,
            "expected_graphdb_semantic_hash": graph_hash,
            "live_graphdb_semantic_hash_before": graph_hash,
            "live_graphdb_semantic_hash_after": graph_hash,
            "publication_authority_reconstruction": authority,
            "repository_semantic_identity_verified": True,
            "repository_unchanged": True,
        },
    }
    for name, document in documents.items():
        _write(directory / name, document)
    return documents


def test_artifact_verifier_independently_closes_all_five_files(tmp_path: Path):
    documents = _artifact(tmp_path)
    result = verify_application_phase01_artifact(tmp_path)
    assert result["status"] == "APPLICATION_READONLY_VERIFIED"
    assert result["expected_graphdb_semantic_hash"] == documents[
        "application-attestation.json"
    ]["expected_graphdb_semantic_hash"]
    assert len(result["artifact_files"]) == 5


@pytest.mark.parametrize(
    ("filename", "field", "value"),
    [
        ("application-attestation.json", "repository_id", None),
        ("golden-query-summary.json", "golden_query_passed", 11),
        ("security-summary.json", "mutation_attack_blocked", 14),
        (
            "graphdb-before-after.json",
            "live_graphdb_semantic_hash_after",
            "0" * 64,
        ),
    ],
)
def test_artifact_verifier_rejects_missing_or_cross_file_mismatched_evidence(
    tmp_path: Path, filename: str, field: str, value: object
):
    documents = _artifact(tmp_path)
    changed = copy.deepcopy(documents[filename])
    if value is None:
        del changed[field]
    else:
        changed[field] = value
    _write(tmp_path / filename, changed)
    with pytest.raises(ArtifactVerificationError):
        verify_application_phase01_artifact(tmp_path)


def test_artifact_verifier_rejects_extra_files_and_sensitive_keys(tmp_path: Path):
    documents = _artifact(tmp_path)
    _write(tmp_path / "unexpected.json", {})
    with pytest.raises(ArtifactVerificationError, match="closed set"):
        verify_application_phase01_artifact(tmp_path)
    (tmp_path / "unexpected.json").unlink()
    changed = copy.deepcopy(documents["security-summary.json"])
    changed["access_token"] = "forbidden"
    _write(tmp_path / "security-summary.json", changed)
    with pytest.raises(ArtifactVerificationError, match="sensitive"):
        verify_application_phase01_artifact(tmp_path)


def test_artifact_verifier_rejects_claimed_authority_failure(tmp_path: Path):
    documents = _artifact(tmp_path)
    changed = copy.deepcopy(documents["application-attestation.json"])
    changed["publication_authority_reconstruction"]["status"] = "FAILED"
    _write(tmp_path / "application-attestation.json", changed)
    with pytest.raises(ArtifactVerificationError, match="schema"):
        verify_application_phase01_artifact(tmp_path)
