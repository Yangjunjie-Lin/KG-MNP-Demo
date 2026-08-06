from __future__ import annotations

import copy

import pytest
from jsonschema import ValidationError

from kg_mnp_demo.modeling.registry import validate_contract
from kg_mnp_demo.modeling.review_actions import validate_review_action
from kg_mnp_demo.modeling.semantic_validation import SemanticValidationError

from ._helpers import load_action, load_proposal


def test_review_action_requires_explicit_human_fields():
    action = load_action("full-confirmation", "action-001.json")
    validate_contract("review-action", action)
    for field in ("decision", "rationale", "decided_at", "reviewer_id"):
        invalid = copy.deepcopy(action)
        invalid.pop(field)
        with pytest.raises(ValidationError):
            validate_contract("review-action", invalid)


def test_action_cannot_target_candidate_and_issue():
    action = load_action("full-confirmation", "action-001.json")
    action["target"]["issue_id"] = "urn:kg-mnp:issue:" + "a" * 64
    with pytest.raises(ValidationError):
        validate_contract("review-action", action)


def test_unknown_target_fails_semantic_validation():
    proposal = load_proposal()
    action = load_action("full-confirmation", "action-001.json")
    action["target"]["candidate_id"] = "urn:kg-mnp:candidate:" + "f" * 64
    with pytest.raises(SemanticValidationError, match="unknown candidate_id"):
        validate_review_action(action, proposal)


def test_decision_id_must_not_be_authored():
    action = load_action("full-confirmation", "action-001.json")
    action["decision_id"] = "authored"
    with pytest.raises(ValidationError):
        validate_contract("review-action", action)
