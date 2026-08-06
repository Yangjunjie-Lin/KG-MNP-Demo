from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.review_log import (
    init_review_decision_log,
    record_review_action,
)
from kg_mnp_demo.modeling.semantic_validation import SemanticValidationError

from ._helpers import dependencies, load_action, load_proposal


def test_record_computes_decision_id_and_rejects_duplicates():
    proposal = load_proposal()
    deps = dependencies()
    draft = init_review_decision_log(
        proposal,
        reviewer_id="urn:kg-mnp:reviewer:professor-001",
        display_name="Reviewer One",
        role="Ontology Reviewer",
        started_at="2026-08-06T00:00:00Z",
        session_label="unit-record",
    )
    action = load_action("full-confirmation", "action-001.json")
    next_log = record_review_action(
        proposal,
        draft,
        action,
        review_policy=deps["review_policy"],
        term_types=deps["term_types"],
    )
    assert len(next_log["decisions"]) == 1
    assert next_log["decisions"][0]["decision_id"].startswith("urn:kg-mnp:review-decision:")
    with pytest.raises(SemanticValidationError, match="duplicate"):
        record_review_action(
            proposal,
            next_log,
            action,
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
        )


def test_record_rejects_wrong_reviewer_and_completed_log():
    proposal = load_proposal()
    deps = dependencies()
    draft = init_review_decision_log(
        proposal,
        reviewer_id="urn:kg-mnp:reviewer:professor-001",
        display_name="Reviewer One",
        role="Ontology Reviewer",
        started_at="2026-08-06T00:00:00Z",
        session_label="unit-record-2",
    )
    action = load_action("full-confirmation", "action-001.json")
    wrong = copy.deepcopy(action)
    wrong["reviewer_id"] = "urn:kg-mnp:reviewer:other"
    with pytest.raises(SemanticValidationError, match="reviewer_id"):
        record_review_action(
            proposal,
            draft,
            wrong,
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
        )
    completed = copy.deepcopy(draft)
    completed["review_session"]["completed_at"] = "2026-08-06T02:00:00Z"
    with pytest.raises(SemanticValidationError, match="completed"):
        record_review_action(
            proposal,
            completed,
            action,
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
        )
