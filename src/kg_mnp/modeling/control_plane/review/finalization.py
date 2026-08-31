"""Fail-closed human review finalization and closure enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ModelingConflictError, ReviewIncompleteError, ReviewPolicyError
from ..prevalidation import verify_prevalidation
from ..proposal import verify_proposal
from ..scope import verify_scope
from ..scope_approval import verify_scope_approval
from .actions import verify_action_chain
from .log import build_decision_log
from .policy import rule_for_scope, verify_review_policy
from .queue import verify_review_queue
from .replay import replay_review

_POSITIVE = {"ACCEPT", "MODIFY_AND_ACCEPT", "REUSE_EXISTING"}


@dataclass(frozen=True)
class FinalizationResult:
    decision_log: dict[str, Any]
    accepted_tbox: tuple[dict[str, Any], ...]
    accepted_mapping: tuple[dict[str, Any], ...]
    accepted_abox: tuple[dict[str, Any], ...]
    accepted_shacl: tuple[dict[str, Any], ...]
    rejected_candidate_ids: tuple[str, ...]
    deferred_candidate_ids: tuple[str, ...]
    resolved_conflict_ids: tuple[str, ...]


def _candidate_index(proposal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["candidate_id"]: item
        for item in [
            *proposal["tbox_candidates"],
            *proposal["mapping_candidates"],
            *proposal["abox_candidates"],
            *proposal["shacl_candidates"],
        ]
    }


def _modified_index(actions: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    return {
        action["modified_candidate"]["candidate_id"]: action["modified_candidate"]
        for action in actions
        if action["decision"] == "MODIFY_AND_ACCEPT" and action["modified_candidate"]
    }


def _enforce_quorum(
    decision: dict[str, Any],
    candidate: dict[str, Any],
    policy: dict[str, Any],
) -> None:
    rule = rule_for_scope(policy, candidate["publication_scope"])
    if len(decision["reviewer_ids"]) < rule["minimum_approvals"]:
        raise ReviewPolicyError(
            f"candidate {candidate['candidate_id']} does not meet minimum approvals"
        )
    roles = set(decision["reviewer_roles"])
    required = set(rule["required_roles"])
    if rule["minimum_approvals"] >= len(required):
        roles_ok = required <= roles
    else:
        roles_ok = bool(required & roles)
    if not roles_ok:
        raise ReviewPolicyError(
            f"candidate {candidate['candidate_id']} does not meet reviewer-role quorum"
        )


def finalize_review(
    *,
    queue: dict[str, Any],
    proposal: dict[str, Any],
    prevalidation: dict[str, Any],
    policy: dict[str, Any],
    actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    coverage_report: dict[str, Any],
    scope: dict[str, Any],
    scope_approval: dict[str, Any],
    current_project_lock_id: str,
) -> FinalizationResult:
    verify_proposal(proposal)
    verify_prevalidation(prevalidation, proposal=proposal)
    verify_review_policy(policy, project_lock_id=current_project_lock_id)
    verify_review_queue(
        queue,
        proposal=proposal,
        prevalidation=prevalidation,
        policy=policy,
    )
    verify_action_chain(actions, queue=queue)
    verify_scope(scope, project_lock_id=current_project_lock_id)
    verify_scope_approval(scope, scope_approval)
    if proposal["project_lock_id"] != current_project_lock_id:
        raise ReviewIncompleteError("proposal is STALE against the current Project Lock")
    if prevalidation["status"] == "FAIL":
        raise ReviewIncompleteError("Formal Prevalidation FAIL cannot be finalized")
    if coverage_report.get("proposal_id") != proposal["proposal_id"]:
        raise ReviewIncompleteError("competency-question coverage report is STALE")
    if coverage_report.get("execution_claimed") is not False:
        raise ReviewIncompleteError("coverage report improperly claims CQ execution")
    replayed = replay_review(queue, actions)
    if replayed["missing_candidate_ids"] or replayed["inconsistent_candidate_ids"]:
        raise ReviewIncompleteError("every candidate requires one consistent final human decision")
    if replayed["requested_evidence_candidate_ids"]:
        raise ReviewIncompleteError("REQUEST_EVIDENCE candidate remains incomplete")
    blocking_conflicts = {
        item["issue_id"] for item in proposal["conflicts"] if item["severity"] == "BLOCKING"
    }
    unresolved = blocking_conflicts - set(replayed["resolved_conflict_ids"])
    if unresolved:
        raise ModelingConflictError("blocking candidate conflicts remain unresolved")
    candidates = _candidate_index(proposal)
    modified = _modified_index(actions)
    accepted: dict[str, list[dict[str, Any]]] = {
        "TBOX": [],
        "MAPPING": [],
        "ABOX": [],
        "SHACL": [],
    }
    accepted_original_ids: set[str] = set()
    rejected: list[str] = []
    deferred: list[str] = []
    for decision in replayed["final_decisions"]:
        original = candidates[decision["candidate_id"]]
        outcome = decision["decision"]
        if outcome in _POSITIVE:
            _enforce_quorum(decision, original, policy)
            if original["support_status"] == "UNSUPPORTED" or any(
                problem["severity"] == "BLOCKING" for problem in original["issues"]
            ):
                raise ReviewPolicyError("unsupported or blocking candidate cannot be accepted")
            effective_id = decision["effective_candidate_id"]
            effective = modified.get(effective_id, original)
            if not effective["evidence_refs"] and not effective["domain_asset_refs"]:
                raise ReviewIncompleteError("accepted candidate lacks evidence closure")
            accepted[effective["publication_scope"]].append(effective)
            accepted_original_ids.add(original["candidate_id"])
        elif outcome in {"REJECT", "MARK_DUPLICATE"}:
            rejected.append(original["candidate_id"])
        elif outcome == "DEFER":
            deferred.append(original["candidate_id"])
        else:
            raise ReviewIncompleteError(f"non-final decision remains: {outcome}")
    for partition in accepted.values():
        for candidate in partition:
            missing = set(candidate["dependency_candidate_refs"]) - accepted_original_ids
            if missing:
                raise ReviewIncompleteError("accepted candidate dependency was not accepted or reused")
    log = build_decision_log(
        queue=queue,
        proposal=proposal,
        prevalidation=prevalidation,
        policy=policy,
        actions=actions,
    )
    return FinalizationResult(
        decision_log=log,
        accepted_tbox=tuple(sorted(accepted["TBOX"], key=lambda item: item["candidate_id"])),
        accepted_mapping=tuple(
            sorted(accepted["MAPPING"], key=lambda item: item["candidate_id"])
        ),
        accepted_abox=tuple(sorted(accepted["ABOX"], key=lambda item: item["candidate_id"])),
        accepted_shacl=tuple(
            sorted(accepted["SHACL"], key=lambda item: item["candidate_id"])
        ),
        rejected_candidate_ids=tuple(sorted(rejected)),
        deferred_candidate_ids=tuple(sorted(deferred)),
        resolved_conflict_ids=tuple(sorted(replayed["resolved_conflict_ids"])),
    )
