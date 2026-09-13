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


def test_prepare_selects_only_direct_public_cq_documents(tmp_path):
    import hashlib
    import json

    from zhigou_toolchain.ontology_io.cli import prepare_cq4oe
    from zhigou_toolchain.ontology_io.cq4oe import CQ4OE_COMMIT

    upstream = tmp_path / "upstream"
    files = []
    for path in ("CQ2Onto/competency_question/allowed.json", "CQ2Onto/competency_question_extra/sibling.json",
                 "CQ2Onto/competency_question/annotations/nested.json", "CQ2Onto/00_gold_standard/target.json"):
        target = upstream / path
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps([{"id": "CQ1", "value": "Which trees?" if path.endswith("allowed.json") else "PRIVATE_SENTINEL"}]).encode()
        target.write_bytes(raw)
        files.append({"path": path, "sha256": hashlib.sha256(raw).hexdigest()})
    (upstream / "asset-lock.json").write_text(json.dumps({"benchmark_id": "cq4oe_0_0_1", "commit": CQ4OE_COMMIT, "files": files}), encoding="utf-8")
    output = tmp_path / "prepared"
    result = prepare_cq4oe(upstream, output, task="cq2onto", limit=10)
    generated = (output / "generation/inputs.json").read_text(encoding="utf-8")
    assert result["sample_count"] == 1 and "PRIVATE_SENTINEL" not in generated
