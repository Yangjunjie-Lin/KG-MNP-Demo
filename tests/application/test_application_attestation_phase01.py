from __future__ import annotations

from kg_mnp_demo.application.attestation import build_application_attestation
from kg_mnp_demo.application.query_registry import QueryRegistry

from ._phase01_helpers import synthetic_binding


def test_attestation_is_verified_only_when_hashes_counts_and_checks_close():
    binding = synthetic_binding()
    graph_hash = binding.graphdb_semantic_hash
    payload = build_application_attestation(
        binding=binding,
        registry=QueryRegistry.load(),
        live_graphdb_semantic_hash_before=graph_hash,
        live_graphdb_semantic_hash_after=graph_hash,
        golden_query_count=10,
        golden_query_passed=10,
        mutation_attack_count=14,
        mutation_attack_blocked=14,
        live_repository_tamper_attack_count=3,
        live_repository_tamper_attack_blocked=3,
        traceability_checks={
            "fact_level": "PASS", "review": "PASS", "evidence": "PASS",
            "source": "PASS", "publication_lineage": "PASS",
        },
        http_runtime={"bind_host": "127.0.0.1", "read_only": True, "golden_http_status": "PASS"},
        result_determinism="PASS",
    )
    assert payload["status"] == "APPLICATION_READONLY_VERIFIED"
    assert payload["repository_unchanged"] is True
    assert payload["repository_id"] == binding.repository_id
    assert payload["expected_graphdb_semantic_hash"] == graph_hash
    assert payload["live_graphdb_semantic_hash_before"] == graph_hash
    assert payload["live_graphdb_semantic_hash_after"] == graph_hash
    assert payload["repository_semantic_identity_verified"] is True
    assert payload["publication_authority_reconstruction"] == {
        "status": "PASS",
        "scenario": "full-confirmation",
        "publication_id": binding.publication_id,
    }


def test_attestation_fails_closed_on_repository_hash_change():
    binding = synthetic_binding()
    payload = build_application_attestation(
        binding=binding,
        registry=QueryRegistry.load(),
        live_graphdb_semantic_hash_before=binding.graphdb_semantic_hash,
        live_graphdb_semantic_hash_after="0" * 64,
        golden_query_count=1,
        golden_query_passed=1,
        mutation_attack_count=1,
        mutation_attack_blocked=1,
        live_repository_tamper_attack_count=3,
        live_repository_tamper_attack_blocked=3,
        traceability_checks={
            "fact_level": "PASS", "review": "PASS", "evidence": "PASS",
            "source": "PASS", "publication_lineage": "PASS",
        },
        http_runtime={"bind_host": "127.0.0.1", "read_only": True, "golden_http_status": "PASS"},
        result_determinism="PASS",
    )
    assert payload["status"] == "FAILED"
    assert payload["repository_unchanged"] is False
    assert payload["repository_semantic_identity_verified"] is False


def test_attestation_fails_closed_when_live_tamper_attack_is_not_blocked():
    binding = synthetic_binding()
    payload = build_application_attestation(
        binding=binding,
        registry=QueryRegistry.load(),
        live_graphdb_semantic_hash_before=binding.graphdb_semantic_hash,
        live_graphdb_semantic_hash_after=binding.graphdb_semantic_hash,
        golden_query_count=1,
        golden_query_passed=1,
        mutation_attack_count=1,
        mutation_attack_blocked=1,
        live_repository_tamper_attack_count=3,
        live_repository_tamper_attack_blocked=2,
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
    assert payload["status"] == "FAILED"
