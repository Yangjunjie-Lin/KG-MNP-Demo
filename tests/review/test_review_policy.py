from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.registry import validate_contract
from kg_mnp_demo.modeling.review_policy import (
    decision_allowed_for_target,
    load_default_review_policy,
    validate_review_policy_semantics,
)
from kg_mnp_demo.modeling.semantic_validation import SemanticValidationError


def test_frozen_review_policy_forbids_defaults_and_auto_confirm():
    policy = load_default_review_policy()
    validate_contract("review-policy", policy)
    validate_review_policy_semantics(policy)
    assert policy["automatic_decisions"] == "FORBIDDEN"
    assert policy["default_decision"] is None
    assert policy["bulk_confirmation"] == "FORBIDDEN"
    assert policy["deprecated_decision_policy"] == "FORBIDDEN_IN_DATASET_MODELING"


def test_decision_matrix_for_candidates_and_issues():
    policy = load_default_review_policy()
    for decision in ("CONFIRM", "MODIFY_AND_CONFIRM", "REJECT", "DEFER"):
        assert decision_allowed_for_target(
            target_kind="candidate", decision=decision, policy=policy
        )
    for decision in ("REJECT", "DEFER"):
        assert decision_allowed_for_target(
            target_kind="issue", decision=decision, policy=policy
        )
    for decision in ("CONFIRM", "MODIFY_AND_CONFIRM", "DEPRECATE"):
        assert not decision_allowed_for_target(
            target_kind="issue", decision=decision, policy=policy
        )


def test_policy_rejects_enabled_auto_confirm():
    policy = copy.deepcopy(load_default_review_policy())
    policy["automatic_decisions"] = "ALLOWED"
    with pytest.raises((SemanticValidationError, Exception)):
        validate_review_policy_semantics(policy)
