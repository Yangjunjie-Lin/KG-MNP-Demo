import json
from pathlib import Path

import pytest
from rdflib import Graph

from zhigou_toolchain.modeling.five_stage.expert_runtime import private_check, safe_view
from zhigou_toolchain.modeling.five_stage.scenario_quality import (
    ScenarioGold,
    actual_units,
    evaluate,
)
from zhigou_toolchain.modeling.five_stage.scenarios import resolve


def test_gold_is_frozen_fixture_not_output_and_projection_is_declared():
    root = Path(__file__).parents[1] / "fixtures/scenario_acceptance"
    for path in root.glob("*.json"):
        gold = ScenarioGold.model_validate_json(path.read_bytes()).model_dump()
        base = {"scenario_id": gold["scenario_id"], "scenario_version": "2.0.0"}
        config = resolve(base)
        score = evaluate(Graph(), gold, config)
        assert score["objects"]["tp"] == 0 and score["objects"]["fn"] > 0
        assert score["objects"]["precision"] is None
        assert score["selected_capabilities"] == config["stages"]["S3"]["selected_capabilities"]


def test_independent_labels_and_metrics_are_not_model_context():
    payload = {"scenario_acceptance": {"labels": [{"key": "PRIVATE_EXPECTED_FACT"}]},
               "scenario_quality": {"correction": "PRIVATE_EXPECTED_FACT"}, "public": "source"}
    with pytest.raises(ValueError, match="PRIVATE"):
        private_check(payload)
    assert "PRIVATE_EXPECTED_FACT" not in json.dumps(safe_view(payload))


def test_typed_matching_excludes_only_generic_individual_declaration():
    graph = Graph().parse(data='''@prefix owl: <http://www.w3.org/2002/07/owl#> .
        <urn:x> a owl:NamedIndividual, <urn:Device> ; <urn:p> "1" .''', format="turtle")
    rows = actual_units(graph)
    assert len(rows) == 2 and {r["kind"] for r in rows} == {"objects", "attributes"}


def test_invalid_independent_term_types_are_rejected_not_scored():
    from zhigou_toolchain.modeling.five_stage.scenario_quality import IndependentLabel
    with pytest.raises(ValueError, match="TERM_TYPE_INVALID"):
        IndependentLabel(kind="attributes", key='["urn:x","urn:p","value",{},null]', capability="core")
