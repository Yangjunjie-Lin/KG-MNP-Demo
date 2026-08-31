from __future__ import annotations

from kg_mnp.modeling.control_plane.terminology import normalize_term


def test_catalog_contains_all_bounded_source_types(prompt04_case: dict) -> None:
    terms = prompt04_case["terminology"]["terms"]
    source_types = {item["source_type"] for item in terms}
    assert {"ONTOLOGY_BASELINE", "APPROVED_SCOPE", "KG_IR", "DOMAIN_PACK"} <= source_types
    assert any(item["lexical_form"] == "label" for item in terms)
    assert all(item["status"] != "CONFIRMED" for item in terms)


def test_normalization_is_unicode_nfc_and_case_insensitive() -> None:
    assert normalize_term("  ENTitY  ") == "entity"
    assert normalize_term("Cafe\u0301") == "café"
