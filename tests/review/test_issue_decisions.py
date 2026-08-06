from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.review_actions import validate_review_action
from kg_mnp_demo.modeling.semantic_validation import SemanticValidationError

from ._helpers import load_action, load_proposal


def test_issue_reject_and_defer_pass():
    proposal = load_proposal("conflicting-values")
    reject = load_action("issue-resolution", "action-003.json")
    defer = load_action("deferred-review", "action-003.json")
    validate_review_action(reject, proposal)
    validate_review_action(defer, proposal)


@pytest.mark.parametrize("decision", ["CONFIRM", "MODIFY_AND_CONFIRM", "DEPRECATE"])
def test_issue_forbidden_decisions_fail(decision):
    proposal = load_proposal("conflicting-values")
    action = copy.deepcopy(load_action("issue-resolution", "action-003.json"))
    action["decision"] = decision
    action.pop("modified_candidate", None)
    with pytest.raises((SemanticValidationError, Exception)):
        validate_review_action(action, proposal)
