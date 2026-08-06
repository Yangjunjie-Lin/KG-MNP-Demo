from __future__ import annotations

from kg_mnp_demo.modeling.review_log import review_status

from ._helpers import load_expected_log, load_proposal


def test_status_reports_coverage_without_mutating_decisions():
    proposal = load_proposal()
    log = load_expected_log("full-confirmation")
    before = len(log["decisions"])
    status = review_status(proposal, log)
    assert status["coverage_complete"] is True
    assert status["candidate_count"] == 5
    assert status["issue_count"] == 0
    assert status["log_completed"] is True
    assert status["can_finalize"] is False
    assert len(log["decisions"]) == before
