"""Operational and semantic review hashes with deterministic replay validation."""

from __future__ import annotations

from typing import Any

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn
from zhigou_toolchain.contracts.registry import validate_contract

from ..errors import ReviewIncompleteError
from ..prevalidation import verify_prevalidation
from ..proposal import verify_proposal
from .actions import verify_action_chain
from .policy import verify_review_policy
from .queue import verify_review_queue
from .replay import replay_review


def build_decision_log(
    *,
    queue: dict[str, Any],
    proposal: dict[str, Any],
    prevalidation: dict[str, Any],
    policy: dict[str, Any],
    actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    verify_review_queue(
        queue,
        proposal=proposal,
        prevalidation=prevalidation,
        policy=policy,
    )
    verify_proposal(proposal)
    verify_prevalidation(prevalidation, proposal=proposal)
    verify_review_policy(policy, project_lock_id=proposal["project_lock_id"])
    verify_action_chain(actions, queue=queue)
    replayed = replay_review(queue, actions)
    operational_log_hash = semantic_hash(
        {
            "review_queue_id": queue["review_queue_id"],
            "action_ids": [action["action_id"] for action in actions],
            "action_hashes": replayed["action_hashes"],
        }
    )
    semantic_decision_hash = semantic_hash(
        {
            "project_lock_id": proposal["project_lock_id"],
            "proposal_id": proposal["proposal_id"],
            "proposal_digest": proposal["content_digest"],
            "prevalidation_report_id": prevalidation["formal_prevalidation_report_id"],
            "prevalidation_digest": prevalidation["content_digest"],
            "review_policy_id": policy["policy_id"],
            "review_policy_digest": policy["content_digest"],
            "final_decisions": replayed["final_decisions"],
            "semantic_action_hashes": replayed["semantic_action_hashes"],
            "resolved_conflict_ids": replayed["resolved_conflict_ids"],
        }
    )
    core = {
        "manifest_kind": "KG_MNP_ONTOLOGY_REVIEW_DECISION_LOG",
        "schema_version": "1.0.0",
        "review_queue_id": queue["review_queue_id"],
        "project_lock_id": proposal["project_lock_id"],
        "proposal_id": proposal["proposal_id"],
        "proposal_digest": proposal["content_digest"],
        "prevalidation_report_id": prevalidation["formal_prevalidation_report_id"],
        "prevalidation_digest": prevalidation["content_digest"],
        "review_policy_id": policy["policy_id"],
        "review_policy_digest": policy["content_digest"],
        "action_ids": [action["action_id"] for action in actions],
        "final_decisions": replayed["final_decisions"],
        "operational_log_hash": operational_log_hash,
        "semantic_decision_hash": semantic_decision_hash,
    }
    log = {
        **core,
        "review_decision_log_id": stable_urn(
            "ontology-review-decision-log",
            {"semantic_decision_hash": semantic_decision_hash},
        ),
        "content_digest": semantic_hash(core),
    }
    validate_contract("ontology-review-decision-log", log)
    return log


def verify_decision_log(
    log: dict[str, Any],
    *,
    queue: dict[str, Any],
    proposal: dict[str, Any],
    prevalidation: dict[str, Any],
    policy: dict[str, Any],
    actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> None:
    validate_contract("ontology-review-decision-log", log)
    expected = build_decision_log(
        queue=queue,
        proposal=proposal,
        prevalidation=prevalidation,
        policy=policy,
        actions=actions,
    )
    if log != expected:
        raise ReviewIncompleteError("review decision log is tampered or STALE")
