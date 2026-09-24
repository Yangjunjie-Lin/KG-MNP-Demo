"""Quote coupling is explicit; source integrity and legacy checks stay strict."""
from copy import deepcopy

import pytest
from jsonschema import ValidationError, validate

from tests.upgrade.test_ontology_io_kernel import (
    REUSE,
    VOCAB,
    Boundary,
    protocol,
    sample,
)
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.assistance import character_chunks
from zhigou_toolchain.ontology_io.adapters import (
    project_task_prediction,
    task_output_schema,
)
from zhigou_toolchain.ontology_io.engine import generate_sample
from zhigou_toolchain.ontology_io.kernel import check_prediction
from zhigou_toolchain.ontology_io.source_quotes import (
    LEGACY,
    PROGRAM,
    bind_unique_source_quote,
    coupled_schema,
    decode_coupled_facts,
    locator_mode,
)


def chunks(text, window=8192, overlap=256):
    return character_chunks(text, text_id="source", text_version="frozen", window=window, overlap=overlap)["chunks"]


def program_protocol(**options):
    return protocol(**options).model_copy(update={"total_run_authorization": {"evidence_locator_mode": PROGRAM}})


def facts(quote="Oak is a tree."):
    return {"facts": [{"triple": ["Oak", "is-a", "Tree"], "quote": quote}]}


def test_profile_is_opt_in_and_does_not_change_legacy_offset_checks():
    assert locator_mode(protocol()) == LEGACY
    s = sample()
    pred, ev = decode_coupled_facts(facts(), typed=False)
    bound = check_prediction(s, pred, VOCAB, ev, chunks(s.text), constrained=True, evidence_locator_mode=PROGRAM)
    assert bound["issues"] == [] and bound["bindings"][0]["locator_origin"] == "PROGRAM_EXACT_UNIQUE_SOURCE_MATCH"
    assert bound["bindings"][0]["model_supplied_offset"] is False
    wrong = [{**ev[0], "start": 1}]
    assert check_prediction(s, pred, VOCAB, wrong, chunks(s.text), constrained=True)["issues"]
    assert check_prediction(s, pred, VOCAB, wrong, chunks(s.text), constrained=True, evidence_locator_mode=PROGRAM)["issues"]


def test_fact_quote_coupling_preserves_every_actual_row_and_assigns_no_fake_offsets():
    raw = {"facts": [facts()["facts"][0], {"triple": ["A", "p", "B"], "quote": "A p B."}, facts()["facts"][0]]}
    original = deepcopy(raw)
    pred, ev = decode_coupled_facts(raw, typed=False)
    assert raw == original and pred["triples"] == [row["triple"] for row in raw["facts"]]
    assert [e["triple_index"] for e in ev] == [0, 1, 2] and all("start" not in e for e in ev)
    assert len(pred["triples"]) == 3  # no dropping or deduplication of predictions


def test_typed_facts_schema_is_bound_in_the_same_actual_row():
    s = sample().model_copy(update={"mode": "SCHEMA_ABOX", "task_id": "schema_guided_abox"})
    raw = {"facts": [{"triple": ["A", "country", "B"], "quote": "A is in B.",
        "schema": {"sub": "City", "rel": "country", "obj": "Country"}}]}
    validate(raw, coupled_schema(task_output_schema(s)))
    pred, ev = decode_coupled_facts(raw, typed=True)
    assert pred == {"triples": [["A", "country", "B"]], "schemas": [raw["facts"][0]["schema"]]}
    assert ev == [{"triple_index": 0, "quote": "A is in B."}]


def test_model_offsets_and_unpaired_evidence_are_forbidden_in_new_wire_schema():
    schema = coupled_schema(task_output_schema(sample()))
    for extra in ({"start": 0}, {"triple_index": 0}):
        raw = facts()
        raw["facts"][0].update(extra)
        with pytest.raises(ValidationError):
            validate(raw, schema)
        with pytest.raises(ValueError, match="FIELDS"):
            decode_coupled_facts(raw, typed=False)


def test_unique_locator_unicode_and_overlap_do_not_weaken_source_proof():
    text = "树🙂 Oak is a tree."
    quote = "Oak is a tree."
    value = bind_unique_source_quote(text, chunks(text), quote)
    assert value["start"] == 3 and value["end"] == len(text) and value["text_hash"] == semantic_hash(text)
    overlap_text = "123456789 unique token 123456789"
    value = bind_unique_source_quote(overlap_text, chunks(overlap_text, 24, 18), "unique token")
    assert value["start"] == 10  # repeated coverage is not multiple source occurrences


@pytest.mark.parametrize("text,quote,reason", [("Oak. Oak.", "Oak.", "AMBIGUOUS"), ("Oak.", "Tree.", "NOT_FOUND")])
def test_ambiguous_and_missing_quotes_never_get_an_invented_location(text, quote, reason):
    with pytest.raises(ValueError, match=reason):
        bind_unique_source_quote(text, chunks(text), quote)


def test_stale_hash_and_cross_window_quote_are_refused():
    text = "abcdefghijklmno"
    stale = chunks(text)
    stale[0]["text_hash"] = "changed"
    with pytest.raises(ValueError, match="FROZEN"):
        bind_unique_source_quote(text, stale, "abc")
    with pytest.raises(ValueError, match="WINDOW"):
        bind_unique_source_quote(text, chunks(text, 5, 1), "cdefghi")


def test_real_kernel_program_profile_preserves_raw_model_output_and_projection(tmp_path):
    client = Boundary([VOCAB, facts()])
    result = generate_sample(sample(), program_protocol(), "TwoAgentKernelV1", tmp_path / "case", client=client)
    assert result["status"] == "GENERATED" and len(client.requests) == 2
    assert result["calls"][1]["proposal"] == facts()
    assert result["kernel"]["evidence"]["issues"] == []
    assert result["kernel"]["evidence_representation"]["facts_rewritten"] is False
    assert project_task_prediction(tmp_path / "case/artifacts", sample())["triples"] == [["Oak", "is-a", "Tree"]]


def test_program_profile_still_rejects_empty_repairs_and_retains_failed_history(tmp_path):
    client = Boundary([VOCAB, facts("invented quote"), {"facts": []}])
    result = generate_sample(sample(), program_protocol(), "TwoAgentKernelV1", tmp_path / "case", client=client)
    assert result["status"] == "FAILED" and result["failure_code"] == "REPAIR_EMPTY_OUTPUT_REJECTED"
    assert result["kernel"]["history"][0]["validation"]["issues"][0]["code"] == "EVIDENCE_QUOTE_UNBOUND"


def test_evidence_binding_remains_active_in_both_ablations(tmp_path):
    for system in ("NoConstrainedExtraction", "NoValidationFeedback"):
        client = Boundary([REUSE, VOCAB, facts()])
        result = generate_sample(sample(True), program_protocol(), system, tmp_path / system, client=client)
        assert result["status"] == "GENERATED" and result["kernel"]["evidence"]["bindings"][0]["start"] == 0
