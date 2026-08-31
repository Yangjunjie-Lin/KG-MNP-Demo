from __future__ import annotations

import copy

import pytest

from kg_mnp.modeling.control_plane.errors import ReviewIncompleteError
from kg_mnp.modeling.control_plane.review.actions import verify_action_chain
from kg_mnp.modeling.control_plane.review.log import verify_decision_log


def test_action_hash_chain_detects_edit_delete_reorder_and_cross_project(prompt04_case: dict) -> None:
    actions = prompt04_case["actions"]
    for invalid in (
        actions[1:],
        list(reversed(actions)),
        [dict(actions[0], project_lock_id="urn:kg-mnp:project-lock:" + "f" * 64), *actions[1:]],
    ):
        with pytest.raises(ReviewIncompleteError):
            verify_action_chain(invalid, queue=prompt04_case["queue"])


def test_decision_log_detects_timestamp_file_tamper(prompt04_case: dict) -> None:
    changed = copy.deepcopy(prompt04_case["finalization"].decision_log)
    changed["operational_log_hash"] = "f" * 64
    with pytest.raises(ReviewIncompleteError, match="tampered"):
        verify_decision_log(
            changed,
            queue=prompt04_case["queue"],
            proposal=prompt04_case["proposal"],
            prevalidation=prompt04_case["prevalidation"],
            policy=prompt04_case["policy"],
            actions=prompt04_case["actions"],
        )


def test_decision_log_rejects_stale_prevalidation_and_policy(prompt04_case: dict) -> None:
    changed_prevalidation = copy.deepcopy(prompt04_case["prevalidation"])
    changed_prevalidation["formal_prevalidation_report_id"] = (
        "urn:kg-mnp:formal-prevalidation-report:" + "f" * 64
    )
    changed_policy = copy.deepcopy(prompt04_case["policy"])
    changed_policy["policy_id"] = "urn:kg-mnp:ontology-review-policy:" + "f" * 64
    for prevalidation, policy in (
        (changed_prevalidation, prompt04_case["policy"]),
        (prompt04_case["prevalidation"], changed_policy),
    ):
        with pytest.raises(ReviewIncompleteError):
            verify_decision_log(
                prompt04_case["finalization"].decision_log,
                queue=prompt04_case["queue"],
                proposal=prompt04_case["proposal"],
                prevalidation=prevalidation,
                policy=policy,
                actions=prompt04_case["actions"],
            )
