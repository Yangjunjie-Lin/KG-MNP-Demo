from __future__ import annotations

from ._helpers import generate


def test_unmapped_field_is_review_only_and_does_not_mint_schema() -> None:
    proposal = generate("unmapped-fields")
    assert any(
        item["path"] == "/experimental/campaign_code"
        for item in proposal["unmapped_fields"]
    )
    assert proposal["schema_delta_candidates"] == []
    assert all(item["review_required"] for item in proposal["unmapped_fields"])

