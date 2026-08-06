from __future__ import annotations

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.modeling.review_log import (
    finalize_review_decision_log,
    init_review_decision_log,
    record_review_action,
)

from ._helpers import dependencies, load_action, load_expected_log, load_proposal


def test_same_actions_different_order_same_final_bytes():
    proposal = load_proposal()
    deps = dependencies()
    actions = [load_action("full-confirmation", f"action-{i:03d}.json") for i in range(1, 6)]
    results = []
    for ordered in (actions, list(reversed(actions))):
        log = init_review_decision_log(
            proposal,
            reviewer_id="urn:kg-mnp:reviewer:professor-001",
            display_name="Reviewer One",
            role="Ontology Reviewer",
            started_at="2026-08-06T00:00:00Z",
            session_label="full-confirmation",
            affiliation="KG-MNP Review Board",
            review_policy=deps["review_policy"],
        )
        for action in ordered:
            log = record_review_action(
                proposal,
                log,
                action,
                review_policy=deps["review_policy"],
                term_types=deps["term_types"],
            )
        final = finalize_review_decision_log(
            proposal,
            log,
            completed_at="2026-08-06T02:00:00Z",
            review_policy=deps["review_policy"],
        )
        results.append(final)
    assert canonical_json_bytes(results[0]) == canonical_json_bytes(results[1])
    assert canonical_json_bytes(results[0]) == canonical_json_bytes(
        load_expected_log("full-confirmation")
    )
