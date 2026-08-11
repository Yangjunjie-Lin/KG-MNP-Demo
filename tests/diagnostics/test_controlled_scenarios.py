from __future__ import annotations

from kg_mnp_demo.diagnostics import reconstruct_diagnostics

from ._helpers import snapshot
from .test_deterministic_diagnostics import requirement


FOCUS = "urn:entity:1"
PATH = "urn:p"


def fact(value, **extra):
    return {"subject": FOCUS, "predicate": PATH, "object": value, **extra}


def candidate(value, outcome, identifier, *, conflict=False):
    return {
        "focus_node": FOCUS,
        "path": PATH,
        "value": value,
        "outcome": outcome,
        "candidate_ref": f"urn:candidate:{identifier}",
        "review_decision_ref": f"urn:review:{identifier}",
        "review_conflict": conflict,
    }


def test_full_confirmation_golden_has_no_false_missingness() -> None:
    package = reconstruct_diagnostics(
        snapshot(requirements=[requirement(path=PATH)], facts=[fact("confirmed")])
    )
    assert package["issues"] == []
    assert package["coverage"]["requirements_evaluated"] == 1


def test_modified_confirmation_uses_only_final_asserted_value() -> None:
    package = reconstruct_diagnostics(
        snapshot(
            requirements=[requirement(path=PATH)],
            facts=[fact("new", value_state="UNCERTAIN")],
            candidates=[candidate("old", "MODIFY_AND_CONFIRM", "old")],
        )
    )
    issue = next(item for item in package["issues"] if item["classification"] == "VALUE_UNCERTAIN")
    assert issue["focus_node"] == FOCUS
    assert issue["path"] == PATH
    assert issue["observed_values"] == ["new"]


def test_rejection_golden_keeps_history_without_requirement_satisfaction() -> None:
    package = reconstruct_diagnostics(
        snapshot(
            requirements=[requirement(path=PATH)],
            facts=[],
            candidates=[candidate("rejected", "REJECT", "rejected")],
        )
    )
    current = [item for item in package["issues"] if item["scope"] == "CURRENT_DIAGNOSTIC"]
    history = [item for item in package["issues"] if item["scope"] == "HISTORICAL_REVIEW_CONTEXT"]
    assert [(item["classification"], item["focus_node"], item["path"]) for item in current] == [
        ("REQUIRED_VALUE_MISSING", FOCUS, PATH)
    ]
    assert [item["classification"] for item in history] == ["REJECTED_CANDIDATE_HISTORY"]
    assert current[0]["authority_basis"][0]["constraint_iri"] == "urn:constraint"


def test_issue_resolution_separates_historical_and_current_conflict() -> None:
    package = reconstruct_diagnostics(
        snapshot(
            requirements=[requirement(path=PATH)],
            facts=[fact("accepted")],
            candidates=[
                candidate("rejected", "REJECT", "a", conflict=True),
                candidate("accepted", "ACCEPT", "b", conflict=True),
            ],
        )
    )
    assert not any(
        item["classification"] == "CONFIRMED_VALUE_CONFLICT"
        for item in package["issues"]
    )
    historical = next(
        item
        for item in package["issues"]
        if item["classification"] == "HISTORICAL_REVIEW_CONFLICT"
    )
    assert historical["scope"] == "HISTORICAL_REVIEW_CONTEXT"
    assert historical["focus_node"] == FOCUS
    assert historical["path"] == PATH
