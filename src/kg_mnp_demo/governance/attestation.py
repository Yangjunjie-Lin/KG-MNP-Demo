"""Phase04 closure evidence built from executed probe records."""

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
    "ILLEGAL_TRANSITION": ("illegal_transition_attempts", "illegal_transition_blocked"),
    "STALE_BINDING": ("stale_binding_attempts", "stale_binding_blocked"),
    "REPLAY": ("replay_attempts", "replay_blocked"),
    "CONCURRENCY": ("concurrency_conflicts", "concurrency_conflicts_blocked"),
    "CSRF": ("csrf_attempts", "csrf_blocked"),
    "XSS": ("xss_attempts", "xss_blocked"),
    "DIRECT_GRAPHDB": ("direct_graphdb_attempts", "direct_graphdb_blocked"),
    "RDF_MUTATION": ("rdf_mutation_attempts", "rdf_mutation_blocked"),
}
NON_AGGREGATED_CATEGORIES = frozenset({"AUTHORITY", "TAMPER", "INPUT", "HTTP"})


def aggregate_probes(probes: Sequence[Mapping[str, Any]]) -> dict[str, int]:
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


def build_application_phase04_attestation(
    *,
    commit_sha: str,
    upstream_verification_mode: str,
    authority: GovernanceAuthority,
    workspace: Mapping[str, Any],
    probes: Sequence[Mapping[str, Any]],
    repository_before_hash: str,
    repository_after_hash: str,
    diagnostic_hash_before: str,
    diagnostic_hash_after: str,
) -> dict[str, Any]:
    reconstructed = validate_governance_workspace_against_authorities(
        workspace, authority
    )
    proposals = reconstructed["proposals"]
    decisions = reconstructed["review_decisions"]
    amendments = reconstructed["approved_amendment_requests"]
    submitted = sum(proposal["status"] != "DRAFT" for proposal in proposals)
    approved = sum(
        decision["decision"] == "APPROVE_FOR_AMENDMENT" for decision in decisions
    )
    rejected = sum(decision["decision"] == "REJECT" for decision in decisions)
    deferred = sum(decision["decision"] == "DEFER" for decision in decisions)
    counts = aggregate_probes(probes)
    repository_unchanged = (
        authority.repository_semantic_hash
        == repository_before_hash
        == repository_after_hash
    )
    diagnostic_unchanged = (
        authority.diagnostic_package_hash
        == diagnostic_hash_before
        == diagnostic_hash_after
    )
    all_probes_close = all(
        counts[attempt] > 0 and counts[attempt] == counts[blocked]
        for attempt, blocked in CATEGORY_FIELDS.values()
    )
    status = (
        "APPLICATION_HUMAN_GOVERNANCE_VERIFIED"
        if (
            repository_unchanged
            and diagnostic_unchanged
            and all_probes_close
            and len(proposals) >= 5
            and submitted == len(proposals)
            and approved >= 3
            and rejected >= 1
            and deferred >= 1
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
        "governance_contract_hash": governance_contract_hash(),
        "governance_workspace_hash": workspace["workspace_hash"],
        "proposals_created": len(proposals),
        "proposals_submitted": submitted,
        "reviews_approved": approved,
        "reviews_rejected": rejected,
        "reviews_deferred": deferred,
        "approved_amendment_requests": len(amendments),
        **counts,
        "repository_expected_hash": authority.repository_semantic_hash,
        "repository_before_hash": repository_before_hash,
        "repository_after_hash": repository_after_hash,
        "repository_unchanged": repository_unchanged,
        "diagnostic_hash_before": diagnostic_hash_before,
        "diagnostic_hash_after": diagnostic_hash_after,
        "diagnostic_unchanged": diagnostic_unchanged,
        "status": status,
    }
    validate_governance_contract("application-phase04-attestation", result)
    return result
