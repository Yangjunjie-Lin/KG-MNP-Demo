"""Review policy loading must fail closed."""

from __future__ import annotations

from pathlib import Path

import pytest

from kg_mnp_demo.modeling import review_policy as review_policy_module
from kg_mnp_demo.modeling.review_policy import ReviewPolicyError, load_review_policy
from kg_mnp_demo.modeling.semantic_validation import (
    SemanticValidationError,
    validate_review_decision_log_semantics,
)

from ._helpers import load_expected_log, load_proposal


def test_missing_review_policy_file_fails_closed(tmp_path: Path, monkeypatch):
    missing = tmp_path / "missing-review-policy.yaml"
    monkeypatch.setattr(review_policy_module, "REVIEW_POLICY_PATH", missing)
    review_policy_module.load_default_review_policy.cache_clear()
    with pytest.raises(ReviewPolicyError, match="cannot load review policy"):
        load_review_policy(missing)
    with pytest.raises(SemanticValidationError, match="review policy load failed closed"):
        validate_review_decision_log_semantics(
            load_expected_log("full-confirmation"),
            load_proposal(),
            review_policy=None,
            require_final=True,
        )
    review_policy_module.load_default_review_policy.cache_clear()


def test_unparseable_review_policy_fails_closed(tmp_path: Path, monkeypatch):
    bad = tmp_path / "bad-policy.yaml"
    bad.write_text("{ this is not: valid: yaml: [[[", encoding="utf-8")
    monkeypatch.setattr(review_policy_module, "REVIEW_POLICY_PATH", bad)
    review_policy_module.load_default_review_policy.cache_clear()
    with pytest.raises((ReviewPolicyError, SemanticValidationError)):
        validate_review_decision_log_semantics(
            load_expected_log("full-confirmation"),
            load_proposal(),
            review_policy=None,
            require_final=True,
        )
    review_policy_module.load_default_review_policy.cache_clear()


def test_schema_invalid_review_policy_fails_closed(tmp_path: Path, monkeypatch):
    bad = tmp_path / "invalid-policy.yaml"
    bad.write_text(
        "policy_id: broken\npolicy_version: '1.0.0'\nautomatic_decisions: ALLOWED\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(review_policy_module, "REVIEW_POLICY_PATH", bad)
    review_policy_module.load_default_review_policy.cache_clear()
    with pytest.raises((ReviewPolicyError, SemanticValidationError)):
        validate_review_decision_log_semantics(
            load_expected_log("full-confirmation"),
            load_proposal(),
            review_policy=None,
            require_final=True,
        )
    review_policy_module.load_default_review_policy.cache_clear()
