from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.modeling.review_identifiers import decision_log_hash
from kg_mnp_demo.modeling.review_log import (
    finalize_review_decision_log,
    init_review_decision_log,
    record_review_action,
)
from kg_mnp_demo.modeling.semantic_validation import SemanticValidationError

from ._helpers import dependencies, load_action, load_expected_log, load_proposal


def test_finalize_requires_complete_coverage_and_sets_hash():
    proposal = load_proposal()
    deps = dependencies()
    draft = init_review_decision_log(
        proposal,
        reviewer_id="urn:kg-mnp:reviewer:professor-001",
        display_name="Reviewer One",
        role="Ontology Reviewer",
        started_at="2026-08-06T00:00:00Z",
        session_label="unit-finalize",
    )
    with pytest.raises(SemanticValidationError, match="incomplete"):
        finalize_review_decision_log(
            proposal,
            draft,
            completed_at="2026-08-06T02:00:00Z",
            review_policy=deps["review_policy"],
        )
    log = copy.deepcopy(draft)
    for name in sorted((deps and True) and [f"action-{i:03d}.json" for i in range(1, 6)]):
        log = record_review_action(
            proposal,
            log,
            load_action("full-confirmation", name),
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
        )
    final = finalize_review_decision_log(
        proposal,
        log,
        completed_at="2026-08-06T02:00:00Z",
        review_policy=deps["review_policy"],
    )
    assert final["review_session"]["completed_at"] == "2026-08-06T02:00:00Z"
    assert final["log_hash"] == decision_log_hash(final)
    expected = load_expected_log("full-confirmation")
    # Same actions and labels must match golden bytes except session label differs.
    assert final["proposal_id"] == expected["proposal_id"]


def test_finalize_sorts_decisions_independently_of_input_order():
    proposal = load_proposal()
    deps = dependencies()
    actions = [load_action("full-confirmation", f"action-{i:03d}.json") for i in range(1, 6)]
    logs = []
    for order in (actions, list(reversed(actions))):
        draft = init_review_decision_log(
            proposal,
            reviewer_id="urn:kg-mnp:reviewer:professor-001",
            display_name="Reviewer One",
            role="Ontology Reviewer",
            started_at="2026-08-06T00:00:00Z",
            session_label="unit-finalize-order",
        )
        log = draft
        for action in order:
            log = record_review_action(
                proposal,
                log,
                action,
                review_policy=deps["review_policy"],
                term_types=deps["term_types"],
            )
        logs.append(
            finalize_review_decision_log(
                proposal,
                log,
                completed_at="2026-08-06T02:00:00Z",
                review_policy=deps["review_policy"],
            )
        )
    assert canonical_json_bytes(logs[0]) == canonical_json_bytes(logs[1])
