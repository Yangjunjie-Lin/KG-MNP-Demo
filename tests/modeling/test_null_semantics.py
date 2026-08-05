from __future__ import annotations

from ._helpers import generate


def test_explicit_null_is_preserved_as_a_distinct_review_issue() -> None:
    proposal = generate("explicit-null")
    issues = [
        issue
        for issue in proposal["issues"]
        if "/subscription/status" in issue["source_paths"]
    ]
    assert any(
        issue.get("details", {}).get("value_state") == "EXPLICIT_NULL"
        for issue in issues
    )
    status_assertions = [
        item
        for item in proposal["candidate_assertions"]
        if item.get("predicate_iri", "").endswith("subscriptionStatusCode")
    ]
    assert status_assertions == []
    assert proposal["input_snapshot"].keys() >= {"input_semantic_hash", "document_id"}

