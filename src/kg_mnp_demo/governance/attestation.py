"""Phase04 closure evidence for separated production and test-fixture tracks."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from .authority_binding import GovernanceAuthority
from .contracts import governance_contract_hash, validate_governance_contract
from .validator import validate_governance_workspace_against_authorities

STAGE08 = "4dc09d9cfb15da3746f108755593ceb9fe805cd7"
PHASE01 = "79b7d34125b0c5cb2d5fe8546e1f4e6a95ca8106"
PHASE02 = "3ef40b9cfbd657b55d8c5f446cfc247335db87f0"
PHASE03 = "06898e8ef3fbe93bd7e7a030f4361c0bef7a76c9"

CATEGORY_FIELDS = {
    "AUTHORITY_LAUNDERING": (
        "authority_laundering_attempts",
        "authority_laundering_blocked",
    ),
    "ILLEGAL_TRANSITION": (
        "illegal_transition_attempts",
        "illegal_transition_blocked",
    ),
    "STALE_BINDING": ("stale_binding_attempts", "stale_binding_blocked"),
    "REPLAY": ("replay_attempts", "replay_blocked"),
    "CONCURRENCY": ("concurrency_attempts", "concurrency_blocked"),
    "CSRF": ("csrf_attempts", "csrf_blocked"),
    "XSS": ("xss_attempts", "xss_blocked"),
    "DIRECT_GRAPHDB": ("direct_graphdb_attempts", "direct_graphdb_blocked"),
    "RDF_MUTATION": ("rdf_mutation_attempts", "rdf_mutation_blocked"),
}
NON_AGGREGATED_CATEGORIES = frozenset({"AUTHORITY", "TAMPER", "INPUT", "HTTP"})


def aggregate_probes(probes: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Derive every security counter from immutable executed probe records."""

    attempts = Counter()
    blocked = Counter()
    identifiers: set[str] = set()
    for probe in probes:
        if set(probe) != {
            "probe_id",
            "category",
            "attack",
            "expected_outcome",
            "actual_outcome",
            "blocked",
            "status",
        }:
            raise ValueError("probe field set mismatch")
        identifier = probe["probe_id"]
        category = probe["category"]
        if identifier in identifiers or category not in {
            *CATEGORY_FIELDS,
            *NON_AGGREGATED_CATEGORIES,
        }:
            raise ValueError("duplicate or unknown probe")
        identifiers.add(identifier)
        attempts[category] += 1
        if (
            probe["blocked"] is True
            and probe["status"] == "PASS"
            and probe["actual_outcome"] == probe["expected_outcome"]
        ):
            blocked[category] += 1
    result: dict[str, int] = {}
    for category, (attempt_field, blocked_field) in CATEGORY_FIELDS.items():
        result[attempt_field] = attempts[category]
        result[blocked_field] = blocked[category]
    return result


def _controlled_summary_is_closed(summary: Mapping[str, Any]) -> bool:
    required = {
        "fixture_type",
        "test_only",
        "production_authority",
        "controlled_fixture_hash",
        "controlled_fixture_diagnostic_package_hash",
        "controlled_fixture_status",
        "diagnostic_issues",
        "proposals_created",
        "proposals_submitted",
        "reviews_approved",
        "reviews_rejected",
        "reviews_deferred",
        "amendment_requests",
        "status",
    }
    return bool(
        set(summary) == required
        and summary["fixture_type"] == "PHASE04_CONTROLLED_DIAGNOSTIC_FIXTURE"
        and summary["test_only"] is True
        and summary["production_authority"] is False
        and summary["controlled_fixture_status"] == "CONTROLLED_DIAGNOSTIC_FIXTURE"
        and summary["status"] == "PASS"
        and summary["diagnostic_issues"] > 0
        and summary["proposals_created"] >= 5
        and summary["proposals_submitted"] == summary["proposals_created"]
        and summary["reviews_approved"] >= 3
        and summary["reviews_rejected"] >= 1
        and summary["reviews_deferred"] >= 1
        and summary["amendment_requests"] == summary["reviews_approved"]
    )


def build_application_phase04_attestation(
    *,
    commit_sha: str,
    upstream_verification_mode: str,
    authority: GovernanceAuthority,
    production_workspace: Mapping[str, Any],
    controlled_scenario_summary: Mapping[str, Any],
    probes: Sequence[Mapping[str, Any]],
    repository_before_hash: str,
    repository_after_hash: str,
    upstream_phase03_hash_before: str,
    upstream_phase03_hash_after: str,
) -> dict[str, Any]:
    """Build success evidence without treating controlled diagnostics as authority."""

    reconstructed = validate_governance_workspace_against_authorities(
        production_workspace, authority
    )
    proposals = reconstructed["proposals"]
    decisions = reconstructed["review_decisions"]
    amendments = reconstructed["approved_amendment_requests"]
    approved = sum(
        decision["decision"] == "APPROVE_FOR_AMENDMENT" for decision in decisions
    )
    rejected = sum(decision["decision"] == "REJECT" for decision in decisions)
    deferred = sum(decision["decision"] == "DEFER" for decision in decisions)
    counts = aggregate_probes(probes)
    controlled_passed = sum(
        probe["blocked"] is True
        and probe["status"] == "PASS"
        and probe["actual_outcome"] == probe["expected_outcome"]
        for probe in probes
    )
    repository_unchanged = (
        authority.repository_semantic_hash
        == repository_before_hash
        == repository_after_hash
    )
    upstream_phase03_unchanged = (
        authority.upstream_phase03_diagnostic_package_hash
        == upstream_phase03_hash_before
        == upstream_phase03_hash_after
    )
    all_required_categories_close = all(
        counts[attempt] > 0 and counts[attempt] == counts[blocked]
        for attempt, blocked in CATEGORY_FIELDS.values()
    )
    controlled_closed = _controlled_summary_is_closed(controlled_scenario_summary)
    fixture_hash = controlled_scenario_summary["controlled_fixture_hash"]
    fixture_package_hash = controlled_scenario_summary[
        "controlled_fixture_diagnostic_package_hash"
    ]
    status = (
        "APPLICATION_HUMAN_GOVERNANCE_VERIFIED"
        if (
            authority.authority_type == "PRODUCTION_EXACT_PHASE03"
            and repository_unchanged
            and upstream_phase03_unchanged
            and all_required_categories_close
            and controlled_passed == len(probes)
            and controlled_closed
            and fixture_hash != authority.upstream_phase03_diagnostic_package_hash
            and fixture_package_hash
            != authority.upstream_phase03_diagnostic_package_hash
            and len(amendments) == approved
        )
        else "FAILED"
    )
    result = {
        "contract_version": "1.0",
        "commit_sha": commit_sha,
        "stage08_baseline": STAGE08,
        "phase01_baseline": PHASE01,
        "phase02_baseline": PHASE02,
        "phase03_baseline": PHASE03,
        "upstream_verification_mode": upstream_verification_mode,
        **authority.binding,
        "upstream_phase03_issues_total": authority.upstream_phase03_issues_total,
        "governance_contract_hash": governance_contract_hash(),
        "production_workspace_hash": production_workspace["workspace_hash"],
        "production_workspace_revision": production_workspace["workspace_revision"],
        "production_proposals_created": len(proposals),
        "production_reviews_approved": approved,
        "production_reviews_rejected": rejected,
        "production_reviews_deferred": deferred,
        "production_amendment_requests": len(amendments),
        "controlled_fixture_hash": fixture_hash,
        "controlled_fixture_diagnostic_package_hash": fixture_package_hash,
        "controlled_fixture_status": controlled_scenario_summary[
            "controlled_fixture_status"
        ],
        "controlled_scenarios_total": len(probes),
        "controlled_scenarios_passed": controlled_passed,
        **counts,
        "repository_expected_hash": authority.repository_semantic_hash,
        "repository_before_hash": repository_before_hash,
        "repository_after_hash": repository_after_hash,
        "repository_unchanged": repository_unchanged,
        "upstream_phase03_hash_before": upstream_phase03_hash_before,
        "upstream_phase03_hash_after": upstream_phase03_hash_after,
        "upstream_phase03_unchanged": upstream_phase03_unchanged,
        "status": status,
    }
    validate_governance_contract("application-phase04-attestation", result)
    return result
