from __future__ import annotations

from kg_mnp_demo.modeling.review_log import init_review_decision_log, review_coverage

from ._helpers import load_expected_log, load_proposal


def test_coverage_reports_undecided_and_complete_states():
    proposal = load_proposal()
    draft = init_review_decision_log(
        proposal,
        reviewer_id="urn:kg-mnp:reviewer:professor-001",
        display_name="Reviewer One",
        role="Ontology Reviewer",
        started_at="2026-08-06T00:00:00Z",
        session_label="coverage",
    )
    incomplete = review_coverage(proposal, draft)
    assert incomplete["coverage_complete"] is False
    assert len(incomplete["undecided_candidate_ids"]) == 5
    complete = review_coverage(proposal, load_expected_log("full-confirmation"))
    assert complete["coverage_complete"] is True
    assert complete["undecided_candidate_ids"] == []
    assert complete["duplicate_target_ids"] == []
    assert complete["unknown_target_ids"] == []
