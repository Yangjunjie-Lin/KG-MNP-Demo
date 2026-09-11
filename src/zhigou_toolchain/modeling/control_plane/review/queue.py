"""Deterministic review queue construction and dependency ordering."""

from __future__ import annotations

from typing import Any

from zhigou_toolchain.contracts.canonical import stable_urn
from zhigou_toolchain.contracts.registry import validate_contract

from ..artifacts import finalize_document, verify_document
from ..errors import ReviewIncompleteError
from ..prevalidation import verify_prevalidation
from ..proposal import verify_proposal
from .policy import rule_for_scope, verify_review_policy

_SCOPE_ORDER = {"TBOX": 2, "SHACL": 3, "MAPPING": 4, "ABOX": 5}


def _candidates(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *proposal["tbox_candidates"],
        *proposal["shacl_candidates"],
        *proposal["mapping_candidates"],
        *proposal["abox_candidates"],
    ]


def _dependency_order(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["candidate_id"]: item for item in candidates}
    remaining = set(by_id)
    emitted: set[str] = set()
    ordered: list[dict[str, Any]] = []
    while remaining:
        ready = [
            by_id[candidate_id]
            for candidate_id in remaining
            if set(by_id[candidate_id]["dependency_candidate_refs"]) <= emitted
        ]
        if not ready:
            ready = [by_id[candidate_id] for candidate_id in remaining]
        ready.sort(key=lambda item: (_SCOPE_ORDER[item["publication_scope"]], item["candidate_id"]))
        selected = ready[0]
        ordered.append(selected)
        emitted.add(selected["candidate_id"])
        remaining.remove(selected["candidate_id"])
    return ordered


def build_review_queue(
    proposal: dict[str, Any],
    prevalidation: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    verify_proposal(proposal)
    verify_prevalidation(prevalidation, proposal=proposal)
    verify_review_policy(policy, project_lock_id=proposal["project_lock_id"])
    report_issues = prevalidation["issues"]
    items: list[dict[str, Any]] = []
    for priority, candidate in enumerate(_dependency_order(_candidates(proposal)), start=1):
        candidate_id = candidate["candidate_id"]
        related = [
            problem
            for problem in [*candidate["issues"], *report_issues]
            if candidate_id in problem.get("candidate_refs", [])
        ]
        blocking = sorted({problem["code"] for problem in related if problem["severity"] == "BLOCKING"})
        missing_dependencies = sorted(
            set(candidate["dependency_candidate_refs"])
            - {item["candidate_id"] for item in _candidates(proposal)}
        )
        blocking.extend(f"MISSING_DEPENDENCY:{value}" for value in missing_dependencies)
        rule = rule_for_scope(policy, candidate["publication_scope"])
        semantic = {
            "proposal_id": proposal["proposal_id"],
            "candidate_id": candidate_id,
            "item_type": "CANDIDATE",
        }
        items.append(
            {
                "queue_item_id": stable_urn("ontology-review-queue-item", semantic),
                "candidate_id": candidate_id,
                "issue_id": None,
                "item_type": "CANDIDATE",
                "publication_scope": candidate["publication_scope"],
                "dependency_refs": candidate["dependency_candidate_refs"],
                "evidence_refs": candidate["evidence_refs"],
                "competency_question_refs": candidate["competency_question_refs"],
                "prevalidation_status": "FAIL" if blocking else "REVIEW_REQUIRED",
                "required_roles": rule["required_roles"],
                "review_state": "BLOCKED" if blocking else "READY_FOR_REVIEW",
                "blocking_reasons": blocking,
                "priority": priority,
            }
        )
    next_priority = len(items) + 1
    for offset, problem in enumerate(proposal["conflicts"]):
        semantic = {
            "proposal_id": proposal["proposal_id"],
            "issue_id": problem["issue_id"],
            "item_type": "CONFLICT",
        }
        items.append(
            {
                "queue_item_id": stable_urn("ontology-review-queue-item", semantic),
                "candidate_id": None,
                "issue_id": problem["issue_id"],
                "item_type": "CONFLICT",
                "publication_scope": None,
                "dependency_refs": problem["candidate_refs"],
                "evidence_refs": problem["evidence_refs"],
                "competency_question_refs": [],
                "prevalidation_status": (
                    "FAIL" if problem["severity"] == "BLOCKING" else "REVIEW_REQUIRED"
                ),
                "required_roles": policy["required_roles"],
                "review_state": "READY_FOR_REVIEW",
                "blocking_reasons": [problem["code"]] if problem["severity"] == "BLOCKING" else [],
                "priority": next_priority + offset,
            }
        )
    core = {
        "manifest_kind": "KG_MNP_ONTOLOGY_REVIEW_QUEUE",
        "schema_version": "1.0.0",
        "project_lock_id": proposal["project_lock_id"],
        "proposal_id": proposal["proposal_id"],
        "proposal_digest": proposal["content_digest"],
        "formal_prevalidation_report_id": prevalidation["formal_prevalidation_report_id"],
        "review_policy_id": policy["policy_id"],
        "items": sorted(items, key=lambda item: (item["priority"], item["queue_item_id"])),
    }
    queue = finalize_document(core, id_field="review_queue_id", urn_kind="ontology-review-queue")
    validate_contract("ontology-review-queue", queue)
    return queue


def verify_review_queue(
    queue: dict[str, Any],
    *,
    proposal: dict[str, Any] | None = None,
    prevalidation: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> None:
    validate_contract("ontology-review-queue", queue)
    verify_document(queue, id_field="review_queue_id", urn_kind="ontology-review-queue")
    priorities = [item["priority"] for item in queue["items"]]
    if priorities != sorted(priorities) or len(priorities) != len(set(priorities)):
        raise ReviewIncompleteError("review queue ordering is not deterministic")
    if proposal is not None and (
        queue["proposal_id"] != proposal["proposal_id"]
        or queue["proposal_digest"] != proposal["content_digest"]
    ):
        raise ReviewIncompleteError("review queue is STALE against proposal")
    if prevalidation is not None and (
        queue["formal_prevalidation_report_id"]
        != prevalidation["formal_prevalidation_report_id"]
    ):
        raise ReviewIncompleteError("review queue is STALE against prevalidation")
    if policy is not None and queue["review_policy_id"] != policy["policy_id"]:
        raise ReviewIncompleteError("review queue is STALE against review policy")
