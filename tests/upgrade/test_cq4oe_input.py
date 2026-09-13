import pytest

from zhigou_toolchain.ontology_io.cq4oe import adapt_cq4oe


@pytest.mark.parametrize("task", ["cq2term", "cq2onto"])
def test_cqs_only_never_derive_scope_from_annotations_or_invent_abox(task):
    sample = adapt_cq4oe([{"id": "CQ1", "value": "Which trees occur in a habitat?", "gold_axioms": "PRIVATE_GOLD"}], sample_id="trees", task=task)
    assert sample.mode == "CQS_TBOX" and sample.text == "" and not sample.records and not sample.initial_triples
    assert sample.competency_questions == ["CQ1: Which trees occur in a habitat?"]
    assert "PRIVATE_GOLD" not in sample.model_dump_json() and "HR" not in sample.model_dump_json()
    assert any("NOT_APPLICABLE" in r for r in sample.requirements)
    assert any("not SPARQL answer correctness" in r for r in sample.requirements)


def test_original_cq_occurrences_are_retained_and_grouping_ignores_gold():
    rows = [{"id": "CQ1", "value": "Which plants?"}, {"id": "CQ2", "value": "Which habitat?"}]
    left = adapt_cq4oe(rows, sample_id="plants", task="cq2onto")
    right = adapt_cq4oe([{**r, "annotation": "SECRET"} for r in reversed(rows)], sample_id="plants", task="cq2onto")
    assert left.group_id == right.group_id
    duplicate = adapt_cq4oe([rows[0], rows[0]], sample_id="plants", task="cq2onto")
    assert duplicate.competency_questions == ["CQ1: Which plants?", "CQ1: Which plants?"]
    assert any("UPSTREAM_REPEATED_CQ_IDS" in r for r in duplicate.requirements)
