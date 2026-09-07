"""Release quorum is a replay of current human decisions, not historic votes."""
from kg_mnp.lifecycle.registry.manifest import init_registry
from kg_mnp.lifecycle.release import create_release_candidate, record_review


def test_withdrawn_approval_cannot_count_after_another_reviewer_approves(tmp_path):
    init_registry(tmp_path)
    candidate = create_release_candidate(
        tmp_path,
        candidate_package_id="urn:kg-mnp:ontology-package:" + "a" * 64,
        required_roles=["RELEASE_MANAGER", "ONTOLOGY_ENGINEER"],
        minimum_distinct_reviewers=2,
    )
    def decide(who, role, decision):
        return record_review(
            tmp_path, candidate["release_candidate_id"], reviewer_id=who,
            reviewer_roles=[role], action=decision, rationale="Explicit human decision",
        )
    decide("alice", "RELEASE_MANAGER", "APPROVE")
    decide("alice", "RELEASE_MANAGER", "REJECT")
    review = decide("bob", "ONTOLOGY_ENGINEER", "APPROVE")
    assert review["quorum_satisfied"] is False
    assert review["finalized"] is False
    review = decide("alice", "RELEASE_MANAGER", "APPROVE")
    assert review["quorum_satisfied"] is True
    assert review["finalized"] is True


def test_one_person_repeated_votes_cannot_increase_distinct_quorum(tmp_path):
    init_registry(tmp_path)
    candidate = create_release_candidate(
        tmp_path, candidate_package_id="urn:kg-mnp:ontology-package:" + "b" * 64,
        required_roles=["RELEASE_MANAGER"], minimum_distinct_reviewers=2,
    )
    for _ in range(3):
        review = record_review(
            tmp_path, candidate["release_candidate_id"], reviewer_id="alice",
            reviewer_roles=["RELEASE_MANAGER"], rationale="Explicit repeated review",
        )
        assert review["quorum_satisfied"] is False
