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
        graphdb_hash_before=graph_hash,
        graphdb_hash_after=graph_hash,
        golden_query_count=10,
        golden_query_passed=10,
        mutation_attack_count=14,
        mutation_attack_blocked=14,
        traceability_checks={
            "fact_level": "PASS", "review": "PASS", "evidence": "PASS",
            "source": "PASS", "publication_lineage": "PASS",
        },
        http_runtime={"bind_host": "127.0.0.1", "read_only": True, "golden_http_status": "PASS"},
        result_determinism="PASS",
    )
    assert payload["status"] == "APPLICATION_READONLY_VERIFIED"
    assert payload["repository_unchanged"] is True


def test_attestation_fails_closed_on_repository_hash_change():
    binding = synthetic_binding()
    payload = build_application_attestation(
        binding=binding,
        registry=QueryRegistry.load(),
        graphdb_hash_before=binding.graphdb_semantic_hash,
        graphdb_hash_after="0" * 64,
        golden_query_count=1,
        golden_query_passed=1,
        mutation_attack_count=1,
        mutation_attack_blocked=1,
        traceability_checks={
            "fact_level": "PASS", "review": "PASS", "evidence": "PASS",
            "source": "PASS", "publication_lineage": "PASS",
        },
        http_runtime={"bind_host": "127.0.0.1", "read_only": True, "golden_http_status": "PASS"},
        result_determinism="PASS",
    )
    assert payload["status"] == "FAILED"
    assert payload["repository_unchanged"] is False
