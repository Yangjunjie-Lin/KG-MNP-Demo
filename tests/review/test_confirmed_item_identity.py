from __future__ import annotations

from kg_mnp_demo.modeling.review_identifiers import confirmed_item_id

from ._helpers import load_expected_package


def test_confirmed_item_ids_self_validate_for_original_and_modified():
    for name in ("full-confirmation", "modified-confirmation"):
        package = load_expected_package(name)
        for item in package["confirmed_abox_decisions"]:
            confirmed = item["confirmed_candidate"]
            expected = confirmed_item_id(
                source_candidate_id=confirmed["source_candidate_id"],
                effective_candidate_id=confirmed["effective_candidate_id"],
                confirmation_mode=confirmed["confirmation_mode"],
                semantic_content=confirmed["semantic_content"],
            )
            assert confirmed["confirmed_item_id"] == expected
            if item["decision"] == "CONFIRM":
                assert confirmed["confirmation_mode"] == "ORIGINAL"
                assert confirmed["source_candidate_id"] == confirmed["effective_candidate_id"]
            if item["decision"] == "MODIFY_AND_CONFIRM":
                assert confirmed["confirmation_mode"] == "MODIFIED"
                assert confirmed["source_candidate_id"] != confirmed["effective_candidate_id"]
