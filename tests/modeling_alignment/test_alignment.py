from __future__ import annotations

from kg_mnp.modeling.control_plane.alignment import align_terms


def test_exact_local_name_ambiguous_and_no_match_are_explicit(prompt04_case: dict) -> None:
    alignments = prompt04_case["alignments"]["alignments"]
    types = {item["alignment_type"] for item in alignments}
    assert {"EXACT_IRI", "EXACT_LABEL", "NORMALIZED_LABEL", "NO_MATCH"} <= types
    label_target = "https://yangjunjie-lin.github.io/KG-MNP-Demo/domain-packs/minimal/terms#label"
    assert any(
        item["target_iri"] == label_target
        and item["alignment_type"] == "NORMALIZED_LABEL"
        for item in alignments
    )
    assert all(item["review_required"] for item in alignments)
    assert all("probability" not in item["score_basis"].casefold() or "not" in item["score_basis"].casefold() for item in alignments)


def test_alignment_repeats_byte_identically(prompt04_case: dict) -> None:
    assert align_terms(prompt04_case["terminology"], prompt04_case["baseline"]) == prompt04_case[
        "alignments"
    ]
