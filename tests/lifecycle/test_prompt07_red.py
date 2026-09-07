from __future__ import annotations

import pytest

from kg_mnp.lifecycle.changes import create_change_proposal, evaluate_change
from kg_mnp.lifecycle.environment import activate, init_environment, rollback
from kg_mnp.lifecycle.errors import LifecycleError
from kg_mnp.lifecycle.registry.manifest import init_registry
from kg_mnp.lifecycle.regression import plan_regression, run_regression
from kg_mnp.lifecycle.release import (
    attest_release,
    create_release_candidate,
    publish_release,
    record_review,
)


def _id(kind: str, char: str) -> str:
    return f"urn:kg-mnp:{kind}:{char * 64}"


def test_regression_without_executor_is_not_success(tmp_path):
    root = tmp_path / "registry"
    init_registry(root)
    plan = plan_regression(
        root,
        base_package_id=_id("ontology-package", "a"),
        candidate_package_id=_id("ontology-package", "b"),
        tests=[
            {
                "test_id": _id("regression-test", "c"),
                "test_category": "PACKAGE_INTEGRITY",
                "assertion_type": "PACKAGE_STATUS",
                "target_package_id": _id("ontology-package", "b"),
                "requirement_level": "REQUIRED",
            }
        ],
    )

    report = run_regression(root, plan)

    assert report["status"] != "PASSED"
    assert report["summary"]["passed"] == 0
    assert report["required_passed"] is False


def test_release_review_quorum_replays_distinct_humans_and_roles(tmp_path):
    root = tmp_path / "registry"
    init_registry(root)
    candidate = create_release_candidate(
        root,
        candidate_package_id=_id("ontology-package", "b"),
        required_roles=["RELEASE_MANAGER", "ONTOLOGY_ENGINEER"],
        minimum_distinct_reviewers=2,
    )

    review = record_review(
        root,
        candidate["release_candidate_id"],
        reviewer_id="alice",
        reviewer_roles=["RELEASE_MANAGER", "ONTOLOGY_ENGINEER"],
        rationale="one human cannot satisfy two-person quorum",
    )

    assert review["quorum_satisfied"] is False


def test_publish_rejects_missing_package_record_and_client_metadata(tmp_path):
    root = tmp_path / "registry"
    init_registry(root)
    candidate = create_release_candidate(
        root,
        candidate_package_id=_id("ontology-package", "b"),
    )
    review = record_review(
        root,
        candidate["release_candidate_id"],
        reviewer_id="alice",
        reviewer_roles=["RELEASE_MANAGER"],
    )

    with pytest.raises(LifecycleError):
        publish_release(
            root,
            candidate,
            review,
            package_name="attacker-controlled-name",
            package_version="99.99.99",
            ontology_iri="urn:attacker:ontology",
            expected_registry_head_hash="0" * 64,
        )


def test_direct_activation_cannot_skip_proposal_and_review(tmp_path):
    root = tmp_path / "registry"
    init_registry(root)
    environment = init_environment(root, environment_name="dev")

    with pytest.raises(LifecycleError):
        activate(
            root,
            environment_id=environment["environment_id"],
            release_id=_id("release", "r"),
            reviewer_id="alice",
            breaking_change_acknowledged=True,
        )


def test_rollback_restores_explicitly_selected_historical_release(tmp_path):
    root = tmp_path / "registry"
    init_registry(root)
    environment = init_environment(root, environment_name="dev")

    with pytest.raises(LifecycleError):
        rollback(
            root,
            environment_id=environment["environment_id"],
            target_release_id=_id("release", "a"),
            reviewer_id="alice",
        )


def test_change_evaluation_missing_closure_cannot_be_complete(tmp_path):
    root = tmp_path / "registry"
    init_registry(root)
    proposal = create_change_proposal(
        root,
        base_package_id=_id("ontology-package", "a"),
    )

    evaluation = evaluate_change(root, proposal["change_proposal_id"])

    assert evaluation["evaluation_status"] != "COMPLETE"


def test_diff_rejects_missing_package_entrypoint(tmp_path):
    from kg_mnp.lifecycle.diff import create_diff

    with pytest.raises(LifecycleError):
        create_diff(tmp_path / "missing-base", tmp_path / "missing-candidate")


def test_review_action_hash_binds_decision_content(tmp_path):
    def create(rationale: str):
        root = tmp_path / rationale
        init_registry(root)
        candidate = create_release_candidate(
            root,
            candidate_package_id=_id("ontology-package", "b"),
        )
        return record_review(
            root,
            candidate["release_candidate_id"],
            reviewer_id="alice",
            reviewer_roles=["RELEASE_MANAGER"],
            rationale=rationale,
        )["actions"][0]["action_hash"]

    assert create("approve because A") != create("approve because B")


def test_attestation_rejects_missing_real_digests(tmp_path):
    root = tmp_path / "registry"
    manifest = init_registry(root)

    with pytest.raises(LifecycleError):
        attest_release(
            root,
            {
                "registry_id": manifest["registry_id"],
                "release_id": _id("release", "r"),
                "package_id": _id("ontology-package", "p"),
            },
        )
