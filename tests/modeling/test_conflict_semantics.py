from __future__ import annotations

from ._helpers import generate


def test_conflict_preserves_all_alternatives_without_a_winner() -> None:
    proposal = generate("conflicting-values")
    conflict = next(issue for issue in proposal["issues"] if issue["issue_type"] == "CONFLICT")
    assert [item["value"] for item in conflict["details"]["alternatives"]] == [
        "ACTIVE",
        "SUSPENDED",
    ]
    assert conflict["details"]["winner"] is None
    assert conflict["blocking"] is True
    assert not any(
        item.get("predicate_iri", "").endswith("subscriptionStatusCode")
        for item in proposal["candidate_assertions"]
    )

