from __future__ import annotations

from kg_mnp_demo.modeling.review_log import init_review_decision_log

from ._helpers import load_proposal


def test_review_init_creates_empty_decisions_without_defaults():
    proposal = load_proposal()
    draft = init_review_decision_log(
        proposal,
        reviewer_id="urn:kg-mnp:reviewer:professor-001",
        display_name="Reviewer One",
        role="Ontology Reviewer",
        started_at="2026-08-06T00:00:00Z",
        session_label="unit-init",
    )
    assert draft["decisions"] == []
    assert draft["proposal_id"] == proposal["proposal_id"]
    assert draft["review_session"]["session_id"].startswith("urn:kg-mnp:review-session:")
    assert "completed_at" not in draft["review_session"]
