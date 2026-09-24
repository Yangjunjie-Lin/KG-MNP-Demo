"""Synthetic source-locator tests; no benchmark answers or model calls."""
from copy import deepcopy

import pytest

from tests.upgrade.test_ontology_io_kernel import VOCAB, Boundary, protocol, sample
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.assistance import character_chunks
from zhigou_toolchain.ontology_io.engine import generate_sample
from zhigou_toolchain.ontology_io.evidence_hints import quote_location_hints
from zhigou_toolchain.ontology_io.kernel import check_prediction


def parts(text):
    return character_chunks(text, text_id="synthetic", text_version="v1", window=8192, overlap=256)["chunks"]


def test_hints_locate_unicode_source_without_fixing_or_approving_model_output():
    text = "树🙂. Oak is a tree."
    evidence = [{"triple_index": 0, "quote": "Oak is a tree.", "start": 99}]
    original = deepcopy(evidence)
    s = sample().model_copy(update={"text": text})
    prediction = {"triples": [["Oak", "is-a", "Tree"]]}
    issues = check_prediction(s, prediction, VOCAB, evidence, parts(text), constrained=True)["issues"]
    hints = quote_location_hints(text, evidence, parts(text), issues)
    assert hints["hints"][0]["verified_position_candidates"] == [{"start": 4, "end": len(text)}]
    assert hints["hints"][0]["proposed_start"] == 99 and evidence == original
    assert hints["authority"] == "SOURCE_LOCATION_ONLY_NOT_GOLD_OR_ENTAILMENT"
    # A hint alone does not make the wrong model locator valid.
    assert check_prediction(s, prediction, VOCAB, evidence, parts(text), constrained=True)["issues"] == issues


def test_ambiguous_and_invented_quotes_are_not_silently_bound():
    text = "Oak. Oak."
    evidence = [{"triple_index": 0, "quote": "Oak.", "start": 99}, {"triple_index": 1, "quote": "invented", "start": 0}]
    issues = [{"code": "EVIDENCE_QUOTE_UNBOUND", "triple_index": index} for index in (0, 1)]
    hints = quote_location_hints(text, evidence, parts(text), issues)["hints"]
    assert hints[0]["exact_source_match_count"] == 2
    assert hints[0]["verified_position_candidates"] == [{"start": 0, "end": 4}, {"start": 5, "end": 9}]
    assert hints[1]["exact_source_match_count"] == 0 and hints[1]["verified_position_candidates"] == []


def test_stale_source_and_diagnostic_size_fail_closed():
    text = "Oak."
    evidence = [{"triple_index": 0, "quote": text, "start": 1}]
    issues = [{"code": "EVIDENCE_QUOTE_UNBOUND", "triple_index": 0}]
    chunks = parts(text)
    chunks[0]["text_hash"] = semantic_hash("different")
    with pytest.raises(ValueError, match="FROZEN"):
        quote_location_hints(text, evidence, chunks, issues)
    with pytest.raises(ValueError, match="BOUND"):
        quote_location_hints(text, evidence, parts(text), issues, max_hints=100)


def test_diagnostic_limits_are_explicit_and_do_not_change_original_issues():
    text = "Oak. " * 6
    evidence = [{"triple_index": i, "quote": "Oak.", "start": 99} for i in range(12)]
    issues = [{"code": "EVIDENCE_QUOTE_UNBOUND", "triple_index": i} for i in range(12)]
    original = deepcopy(issues)
    result = quote_location_hints(text, evidence, parts(text), issues)
    assert len(result["hints"]) == 8 and result["omitted_diagnostic_count"] == 4 and issues == original
    assert all(len(row["verified_position_candidates"]) == 4 and row["exact_source_match_count"] == 6 for row in result["hints"])


def test_repair_receives_source_offsets_and_empty_repair_is_still_rejected(tmp_path):
    bad = {"prediction": {"triples": [["Oak", "is-a", "Tree"]]}, "evidence": [{"triple_index": 0, "quote": "Oak is a tree.", "start": 1}]}
    empty = {"prediction": {"triples": []}, "evidence": []}
    client = Boundary([VOCAB, bad, empty])
    result = generate_sample(sample(), protocol(), "TwoAgentKernelV1", tmp_path / "run", client=client)
    assert result["status"] == "FAILED" and result["failure_code"] == "REPAIR_EMPTY_OUTPUT_REJECTED"
    feedback = client.requests[-1]["content"]["feedback"]
    assert feedback["quote_location_hints"]["hints"][0]["verified_position_candidates"] == [{"start": 0, "end": 14}]
    assert client.requests[-1]["content"]["previous"] == bad["prediction"]
    assert "instance-of" in client.requests[0]["instruction"] and "subclass_of" in client.requests[0]["instruction"]
