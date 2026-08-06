from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.confirmation import PackageBuildError, build_confirmed_modeling_package
from kg_mnp_demo.modeling.review_log import (
    finalize_review_decision_log,
    init_review_decision_log,
    record_review_action,
)

from ._helpers import dependencies, load_action, load_input, load_proposal


def _log_with_rejected_subject():
    proposal = load_proposal()
    deps = dependencies()
    subscription = next(
        item
        for item in proposal["candidate_entities"]
        if "ServiceSubscription" in item["class_iri"]
    )
    log = init_review_decision_log(
        proposal,
        reviewer_id="urn:kg-mnp:reviewer:professor-001",
        display_name="Reviewer One",
        role="Ontology Reviewer",
        started_at="2026-08-06T00:00:00Z",
        session_label="closure-reject-subject",
        affiliation="KG-MNP Review Board",
        review_policy=deps["review_policy"],
    )
    for index in range(1, 6):
        action = load_action("full-confirmation", f"action-{index:03d}.json")
        if action["target"].get("candidate_id") == subscription["candidate_id"]:
            action = copy.deepcopy(action)
            action["decision"] = "REJECT"
            action["rationale"] = "Reject subject while leaving dependent assertions confirmed."
        log = record_review_action(
            proposal,
            log,
            action,
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
        )
    return finalize_review_decision_log(
        proposal,
        log,
        completed_at="2026-08-06T02:00:00Z",
        review_policy=deps["review_policy"],
    )


def test_confirmed_relation_with_rejected_subject_fails():
    deps = dependencies()
    with pytest.raises(PackageBuildError, match="non-confirmed subject"):
        build_confirmed_modeling_package(
            load_input(),
            load_proposal(),
            _log_with_rejected_subject(),
            deps["ontology_baseline"],
            deps["mapping_rules"],
            deps["terminology_profile"],
            deps["proposal_policy"],
            deps["review_policy"],
            term_types=deps["term_types"],
        )
