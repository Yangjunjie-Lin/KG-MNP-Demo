from pathlib import Path

import pytest
from defusedxml import ElementTree as ET

from zhigou_toolchain.ontology_io.oskgc import (
    adapt_oskgc,
    native_evaluator,
    score_native,
)

RAW = (Path(__file__).resolve().parents[1] / "fixtures/ontology_io/oskgc_base_evaluator.py.txt").read_bytes()
HIERARCHY = ({"Thing": ["Thing"], "City": ["Thing", "City"], "Country": ["Thing", "Country"]}, {"Thing": 2, "City": 0, "Country": 0}, {"City": 1, "Country": 1})


def test_input_reads_category_schema_not_sample_gold():
    entry = ET.fromstring('<entry id="1_Airport_train_1" category="1_Airport"><text>City A is in country B.</text><triples>PRIVATE_GOLD</triples><schemas>PRIVATE_TYPES</schemas></entry>')
    schema = {"id": "1_Airport", "entity type": [{"id": "City", "label": "City", "private_gold": "NO"}],
        "relation": [{"id": "country", "label": "country", "domain": "City", "range": "Country"}], "hierarchy": [], "private_gold": "NO"}
    sample = adapt_oskgc(entry, schema)
    assert sample.mode == "SCHEMA_ABOX" and "PRIVATE" not in sample.model_dump_json()
    assert "private_gold" not in sample.model_dump_json() and "country" in sample.allowed_schema["relations"][0]["id"]


def test_native_ss_root_unknown_first_relation_and_extra_predictions_behaviour():
    evaluator = native_evaluator(RAW)
    assert evaluator.calculate_metrics([], []) == (0, 0, 0)  # Native empty != LLMs4OL empty.
    assert evaluator.calculate_ss_score(*HIERARCHY, "Unknown", "Unknown") == (None, 0, 1)
    assert evaluator.calculate_ss_score(*HIERARCHY, "City", "Unknown") == (None, None, 0)
    targets = {"1_Airport_test_1": {"triples": [["a", "country", "b"]], "schemas": [["City", "country", "Country"]]}}
    prediction = {"1_Airport_test_1": {"triples": [["A", "country", "B"]], "schemas": [{"sub": "City", "rel": "country", "obj": "Country"}]}}
    result = score_native(RAW, prediction, targets, HIERARCHY)
    assert result["metrics"] == {"Precision": 1, "Recall": 1, "micro_F1": 1, "macro_F1": 1, "SS": 1}
    prediction["1_Airport_test_1"]["schemas"] *= 2
    assert score_native(RAW, prediction, targets, HIERARCHY)["metrics"]["SS"] == .5
    # No private gold rows/schema labels copied into a public score receipt.
    assert "label_schemas" not in str(result) and "triples" not in result


def test_native_global_union_micro_is_not_summed_per_record_true_positives():
    target = {"triples": [["a", "p", "b"]], "schemas": []}
    predictions = {"1_Airport_test_1": {"triples": [["a", "p", "b"]], "schemas": []},
        "1_Airport_test_2": {"triples": [], "schemas": []}}
    targets = {key: target for key in predictions}
    result = score_native(RAW, predictions, targets, HIERARCHY)
    assert result["metrics"]["micro_F1"] == 1
    assert result["metrics"]["macro_F1"] == .5
    assert result["metrics"]["SS"] == 0
    with pytest.raises(ValueError, match="INVENTORY"):
        score_native(RAW, {"1_Airport_test_1": predictions["1_Airport_test_1"]}, targets, HIERARCHY)


def test_changed_native_scorer_is_rejected():
    with pytest.raises(ValueError, match="SCORER_CHANGED"):
        native_evaluator(RAW + b"\n# changed")
