"""Application Phase 02 closure attestation builder."""

from __future__ import annotations

from typing import Any

from .binding import PHASE01_BASELINE_SHA, STAGE08_BASELINE_SHA, WorkbenchBinding
from .contracts import validate_workbench_contract


def build_workbench_attestation(
    *,
    commit_sha: str,
    binding: WorkbenchBinding,
    frontend_build_hash: str,
    runtime_policy_hash: str,
    repository_hash_before: str,
    repository_hash_after: str,
    browser: dict[str, Any],
    security: dict[str, Any],
    result_fidelity_status: str,
    traceability_view_status: str,
) -> dict[str, Any]:
    closure = (
        repository_hash_before
        == repository_hash_after
        == binding.repository_semantic_hash
        and browser.get("status") == "PASS"
        and browser.get("golden_scenario_count")
        == browser.get("golden_scenario_passed")
        == 4
        and browser.get("external_requests") == []
        and browser.get("service_worker_count") == 0
        and browser.get("local_storage_entry_count") == 0
        and browser.get("indexed_db_count") == 0
        and security.get("status") == "PASS"
        and security.get("xss_attack_count")
        == security.get("xss_attack_blocked")
        and security.get("relay_attack_count")
        == security.get("relay_attack_blocked")
        and security.get("authority_tamper_attack_count")
        == security.get("authority_tamper_attack_blocked")
        and security.get("direct_graphdb_access_attempt_count")
        == security.get("direct_graphdb_access_blocked_count")
        and result_fidelity_status == "PASS"
        and traceability_view_status == "PASS"
    )
    payload = {
        "contract_version": "1.0",
        "commit_sha": commit_sha,
        "foundation_stage08_baseline": STAGE08_BASELINE_SHA,
        "phase01_baseline_sha": PHASE01_BASELINE_SHA,
        "phase01_attestation_hash": binding.phase01_attestation_hash,
        "phase01_attestation_status": binding.phase01_attestation_status,
        "publication_id": binding.publication_id,
        "publication_semantic_hash": binding.publication_semantic_hash,
        "repository_hash_expected": binding.repository_semantic_hash,
        "repository_hash_before": repository_hash_before,
        "repository_hash_after": repository_hash_after,
        "repository_unchanged": repository_hash_before == repository_hash_after,
        "query_registry_hash": binding.query_registry_hash,
        "frontend_build_hash": frontend_build_hash,
        "runtime_policy_hash": runtime_policy_hash,
        "browser_name": browser["browser_name"],
        "browser_version": browser["browser_version"],
        "browser_revision": browser["browser_revision"],
        "golden_scenario_count": browser["golden_scenario_count"],
        "golden_scenario_passed": browser["golden_scenario_passed"],
        "xss_attack_count": security["xss_attack_count"],
        "xss_attack_blocked": security["xss_attack_blocked"],
        "relay_attack_count": security["relay_attack_count"],
        "relay_attack_blocked": security["relay_attack_blocked"],
        "authority_tamper_attack_count": security[
            "authority_tamper_attack_count"
        ],
        "authority_tamper_attack_blocked": security[
            "authority_tamper_attack_blocked"
        ],
        "external_request_count": len(browser["external_requests"]),
        "direct_graphdb_access_attempt_count": security[
            "direct_graphdb_access_attempt_count"
        ],
        "direct_graphdb_access_blocked_count": security[
            "direct_graphdb_access_blocked_count"
        ],
        "service_worker_count": browser["service_worker_count"],
        "local_storage_entry_count": browser["local_storage_entry_count"],
        "indexed_db_count": browser["indexed_db_count"],
        "result_fidelity_status": result_fidelity_status,
        "traceability_view_status": traceability_view_status,
        "status": (
            "APPLICATION_WORKBENCH_VERIFIED" if closure else "FAILED"
        ),
    }
    if closure:
        validate_workbench_contract("attestation", payload)
    return payload
