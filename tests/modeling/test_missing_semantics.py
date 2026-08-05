from __future__ import annotations

from ._helpers import generate


def test_declared_missing_creates_issue_without_a_fabricated_value() -> None:
    proposal = generate("declared-missing")
    matching = [
        issue
        for issue in proposal["issues"]
        if issue["issue_type"] == "MISSING_INFORMATION"
        and "/subscription/status" in issue["source_paths"]
    ]
    assert matching
    assert any(issue.get("details", {}).get("missing_id") for issue in matching)
    rendered = repr(proposal)
    assert "hasDebt" not in rendered
    assert "noContract" not in rendered

