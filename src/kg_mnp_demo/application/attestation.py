"""Application Phase 01 attestation construction and validation."""

from __future__ import annotations

from typing import Any

from .contracts import validate_application_contract
from .publication_binding import PublicationBinding
from .query_registry import QueryRegistry


def build_application_attestation(
    *,
    binding: PublicationBinding,
    registry: QueryRegistry,
    graphdb_hash_before: str,
    graphdb_hash_after: str,
    golden_query_count: int,
    golden_query_passed: int,
    mutation_attack_count: int,
    mutation_attack_blocked: int,
    traceability_checks: dict[str, str],
    http_runtime: dict[str, Any],
    result_determinism: str,
) -> dict[str, Any]:
    verified = (
        graphdb_hash_before == graphdb_hash_after == binding.graphdb_semantic_hash
        and golden_query_count > 0
        and golden_query_count == golden_query_passed
        and mutation_attack_count > 0
        and mutation_attack_count == mutation_attack_blocked
        and set(traceability_checks.values()) == {"PASS"}
        and http_runtime == {
            "bind_host": "127.0.0.1",
            "read_only": True,
            "golden_http_status": "PASS",
        }
        and result_determinism == "PASS"
    )
    payload = {
        "contract_version": "1.0",
        "publication_id": binding.publication_id,
        "publication_semantic_hash": binding.publication_semantic_hash,
        "graphdb_semantic_hash_before": graphdb_hash_before,
        "graphdb_semantic_hash_after": graphdb_hash_after,
        "repository_unchanged": verified,
        "query_registry_hash": registry.document_hash,
        "golden_query_count": golden_query_count,
        "golden_query_passed": golden_query_passed,
        "mutation_attack_count": mutation_attack_count,
        "mutation_attack_blocked": mutation_attack_blocked,
        "traceability_checks": traceability_checks,
        "http_runtime": http_runtime,
        "result_determinism": result_determinism,
        "status": "APPLICATION_READONLY_VERIFIED" if verified else "FAILED",
    }
    if verified:
        validate_application_contract("application-phase01-attestation", payload)
    return payload
