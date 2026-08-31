from __future__ import annotations

import copy

import pytest

from kg_mnp.modeling.control_plane.errors import (
    ReviewIncompleteError,
    ReviewPolicyError,
)
from kg_mnp.modeling.control_plane.review.actions import (
    build_review_action,
    rebuild_candidate_revision,
    verify_action_chain,
)
from kg_mnp.modeling.control_plane.review.log import build_decision_log
from kg_mnp.modeling.control_plane.review.queue import build_review_queue
from kg_mnp.modeling.control_plane.review.replay import review_status


def test_queue_dependency_order_and_replay_are_deterministic(prompt04_case: dict) -> None:
    queue = prompt04_case["queue"]
    assert queue == build_review_queue(
        prompt04_case["proposal"],
        prompt04_case["prevalidation"],
        prompt04_case["policy"],
    )
    positions = {item["candidate_id"]: item["priority"] for item in queue["items"]}
    for item in queue["items"]:
        if item["candidate_id"]:
            assert all(positions[dependency] < item["priority"] for dependency in item["dependency_refs"])
    assert review_status(queue, prompt04_case["actions"])["complete"] is True


def test_action_delete_reorder_tamper_and_provider_self_review_fail(prompt04_case: dict) -> None:
    actions = prompt04_case["actions"]
    with pytest.raises(ReviewIncompleteError):
        verify_action_chain(actions[1:])
    tampered = copy.deepcopy(actions)
    tampered[0]["rationale"] = "changed"
    with pytest.raises(ReviewIncompleteError, match="semantic hash"):
        verify_action_chain(tampered)
    first_item = next(item for item in prompt04_case["queue"]["items"] if item["candidate_id"])
    with pytest.raises(ReviewPolicyError, match="provider"):
        build_review_action(
            queue=prompt04_case["queue"],
            proposal=prompt04_case["proposal"],
            policy=prompt04_case["policy"],
            existing_actions=[],
            decision="ACCEPT",
            reviewer_id="provider",
            reviewer_role="provider",
            rationale="forbidden",
            candidate_id=first_item["candidate_id"],
        )


def test_semantic_log_hash_ignores_operational_timestamp(prompt04_case: dict) -> None:
    actions = []
    for original in prompt04_case["actions"]:
        rebuilt = build_review_action(
            queue=prompt04_case["queue"],
            proposal=prompt04_case["proposal"],
            policy=prompt04_case["policy"],
            existing_actions=actions,
            decision=original["decision"],
            reviewer_id=original["reviewer_id"],
            reviewer_role=original["reviewer_role"],
            rationale=original["rationale"],
            candidate_id=original["candidate_id"],
            decided_at="2030-01-01T00:00:00Z",
        )
        actions.append(rebuilt)
    first = prompt04_case["finalization"].decision_log
    second = build_decision_log(
        queue=prompt04_case["queue"],
        proposal=prompt04_case["proposal"],
        prevalidation=prompt04_case["prevalidation"],
        policy=prompt04_case["policy"],
        actions=actions,
    )
    assert first["semantic_decision_hash"] == second["semantic_decision_hash"]
    assert first["review_decision_log_id"] == second["review_decision_log_id"]
    assert first["operational_log_hash"] != second["operational_log_hash"]


def test_modified_candidate_gets_new_core_id_and_revalidation(prompt04_case: dict) -> None:
    original = prompt04_case["proposal"]["abox_candidates"][0]
    body = copy.deepcopy(original["body"])
    body["label"] = f"{body.get('label') or 'neutral entity'} reviewed revision"
    replacement = {"body": body, "rationale": original["rationale"] + " reviewed revision"}
    revised = rebuild_candidate_revision(
        original,
        replacement,
        scope=prompt04_case["scope"],
        evidence_ids=set(prompt04_case["input_bundle"]["evidence_record_ids"]),
        baseline_element_ids={item["element_id"] for item in prompt04_case["baseline"]["elements"]},
        candidate_ids={
            item["candidate_id"]
            for item in [
                *prompt04_case["proposal"]["tbox_candidates"],
                *prompt04_case["proposal"]["mapping_candidates"],
                *prompt04_case["proposal"]["abox_candidates"],
            ]
        },
    )
    assert revised["candidate_id"] != original["candidate_id"]
    assert revised["issues"] == []
