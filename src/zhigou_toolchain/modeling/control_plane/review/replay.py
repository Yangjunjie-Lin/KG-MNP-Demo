"""Pure replay of an append-only action chain into semantic decisions."""

from __future__ import annotations

from typing import Any

from .actions import verify_action_chain
from .queue import verify_review_queue

_TERMINAL = {
    "ACCEPT",
    "MODIFY_AND_ACCEPT",
    "REJECT",
    "DEFER",
    "REUSE_EXISTING",
    "MARK_DUPLICATE",
}


def replay_review(
    queue: dict[str, Any],
    actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    verify_review_queue(queue)
    verify_action_chain(actions, queue=queue)
    latest_by_reviewer: dict[str, dict[str, dict[str, Any]]] = {}
    resolved_conflicts: set[str] = set()
    requested_evidence: set[str] = set()
    for action in actions:
        candidate_id = action["candidate_id"]
        issue_id = action["issue_id"]
        if issue_id and action["decision"] == "RESOLVE_CONFLICT":
            resolved_conflicts.add(issue_id)
        if candidate_id and action["decision"] == "REQUEST_EVIDENCE":
            requested_evidence.add(candidate_id)
        if candidate_id and action["decision"] in _TERMINAL:
            latest_by_reviewer.setdefault(candidate_id, {})[action["reviewer_id"]] = action
            requested_evidence.discard(candidate_id)
    final_decisions: list[dict[str, Any]] = []
    inconsistent: list[str] = []
    for item in queue["items"]:
        candidate_id = item["candidate_id"]
        if candidate_id is None:
            continue
        reviewer_actions = latest_by_reviewer.get(candidate_id, {})
        if not reviewer_actions:
            continue
        decisions = {action["decision"] for action in reviewer_actions.values()}
        effective_ids = {
            action["modified_candidate"]["candidate_id"]
            if action["decision"] == "MODIFY_AND_ACCEPT"
            else candidate_id
            for action in reviewer_actions.values()
        }
        if len(decisions) != 1 or len(effective_ids) != 1:
            inconsistent.append(candidate_id)
            continue
        ordered = sorted(reviewer_actions.values(), key=lambda action: action["reviewer_id"])
        final_decisions.append(
            {
                "candidate_id": candidate_id,
                "decision": next(iter(decisions)),
                "effective_candidate_id": next(iter(effective_ids)),
                "reviewer_ids": [action["reviewer_id"] for action in ordered],
                "reviewer_roles": sorted({action["reviewer_role"] for action in ordered}),
            }
        )
    candidate_ids = {
        item["candidate_id"] for item in queue["items"] if item["candidate_id"] is not None
    }
    decided_ids = {item["candidate_id"] for item in final_decisions}
    return {
        "final_decisions": sorted(final_decisions, key=lambda item: item["candidate_id"]),
        "missing_candidate_ids": sorted(candidate_ids - decided_ids),
        "inconsistent_candidate_ids": sorted(inconsistent),
        "requested_evidence_candidate_ids": sorted(requested_evidence),
        "resolved_conflict_ids": sorted(resolved_conflicts),
        "semantic_action_hashes": [action["semantic_action_hash"] for action in actions],
        "action_hashes": [action["action_hash"] for action in actions],
    }


def review_status(
    queue: dict[str, Any],
    actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    result = replay_review(queue, actions)
    total = sum(item["candidate_id"] is not None for item in queue["items"])
    decided = len(result["final_decisions"])
    return {
        "review_queue_id": queue["review_queue_id"],
        "candidate_count": total,
        "decided_count": decided,
        "remaining_count": total - decided,
        "complete": not result["missing_candidate_ids"]
        and not result["inconsistent_candidate_ids"],
        **result,
    }
