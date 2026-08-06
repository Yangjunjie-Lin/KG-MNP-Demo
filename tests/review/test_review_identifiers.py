from __future__ import annotations

from kg_mnp_demo.modeling.review_identifiers import (
    confirmed_package_id,
    decision_log_hash,
    decision_log_id,
    package_semantic_hash,
    review_decision_id,
    review_session_id,
)

from ._helpers import load_expected_log, load_expected_package, load_proposal


def test_session_and_decision_ids_are_stable_urns():
    proposal = load_proposal()
    session = review_session_id(
        proposal_id=proposal["proposal_id"],
        proposal_semantic_hash=proposal["proposal_semantic_hash"],
        reviewer_id="urn:kg-mnp:reviewer:professor-001",
        started_at="2026-08-06T00:00:00Z",
        review_policy_id="kg-mnp-stage05-review",
        review_policy_version="1.0.0",
        session_label="full-confirmation",
    )
    assert session.startswith("urn:kg-mnp:review-session:")
    decision = review_decision_id(
        proposal_id=proposal["proposal_id"],
        target_id=proposal["candidate_entities"][0]["candidate_id"],
        decision="CONFIRM",
        rationale="stable",
        reviewer_id="urn:kg-mnp:reviewer:professor-001",
        decided_at="2026-08-06T00:01:00Z",
        evidence_refs=["e1"],
    )
    assert decision.startswith("urn:kg-mnp:review-decision:")


def test_log_and_package_hashes_self_validate():
    log = load_expected_log("full-confirmation")
    assert log["log_hash"] == decision_log_hash(log)
    assert log["decision_log_id"] == decision_log_id(
        proposal_id=log["proposal_id"],
        proposal_semantic_hash=log["proposal_semantic_hash"],
        reviewer_id=log["reviewer"]["reviewer_id"],
        session_id=log["review_session"]["session_id"],
        review_policy_version="1.0.0",
    )
    package = load_expected_package("full-confirmation")
    assert package["package_semantic_hash"] == package_semantic_hash(package)
    assert package["package_id"] == confirmed_package_id(package)
