"""Frozen MNP examples remain evaluable without a second publishing platform."""
import copy
import importlib.util
import inspect
import json
from pathlib import Path

import pytest

from kg_mnp.application import assessment_service
from kg_mnp.application.assessment_service import AssessmentService
from kg_mnp.application.errors import ApplicationError
from kg_mnp.trace_graph import edges_exist_in_graph

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "domain_packs/mnp/fixtures/inputs/case03.json"


@pytest.fixture(scope="module")
def assessed():
    payload = json.loads(INPUT.read_bytes())
    return AssessmentService().assess_execution(payload)


def test_case03_rule_and_evidence_bindings_are_preserved(assessed):
    assert assessed.exit_code == 0 and assessed.decision == "BLOCKED"
    reason = assessed.evaluation["blocking_reasons"][0]
    assert reason["reason_code"] == "ACTIVE_CONTRACT_RESTRICTION"
    assert reason["rule_id"] == "MNP-ELIG-004" and reason["rule_version"] == "1.0"
    assert reason["regulatory_clause"] == "REG-MNP-CLAUSE-04"
    assert reason["action_code"] == "WAIT_OR_TERMINATE_CONTRACT"
    assert reason["evidence"]["evidence_id"]


def test_dual_validation_and_trace_use_real_graph(assessed):
    validation = assessed.response["validations"]
    assert validation["input_graph"]["status"] == validation["assessment_graph"]["status"] == "PASSED"
    assert assessed.publishable is True  # Historical eligibility result, not a toolchain Release.
    trace = assessed.response["trace_subgraph"]
    assert {"usesEvidence", "evaluatedByRule", "usesRuleVersion", "operationalizesClause", "recommendsAction"} <= {e["predicate"] for e in trace["edges"]}
    assert edges_exist_in_graph(assessed.assessment_graph, trace) == []


def test_repeatable_reader_leaves_source_and_workspace_unchanged(tmp_path, monkeypatch):
    before = INPUT.read_bytes()
    payload = json.loads(before)
    original = copy.deepcopy(payload)
    monkeypatch.chdir(tmp_path)
    a = AssessmentService().assess_execution(payload)
    b = AssessmentService().assess_execution(payload)
    assert a.decision == b.decision
    assert a.evaluation["blocking_reasons"] == b.evaluation["blocking_reasons"]
    assert a.response["trace_subgraph"]["edges"] == b.response["trace_subgraph"]["edges"]
    assert a.instance_graph.serialize(format="turtle") == b.instance_graph.serialize(format="turtle")
    assert payload == original and INPUT.read_bytes() == before
    assert not list(tmp_path.iterdir())


def test_invalid_input_never_publishes(tmp_path, monkeypatch):
    source = ROOT / "domain_packs/mnp/fixtures/inputs/invalid_missing_source.json"
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ApplicationError) as failure:
        AssessmentService().assess_execution(json.loads(source.read_bytes()))
    assert failure.value.code.value == "INPUT_SCHEMA_ERROR"
    assert not list(tmp_path.iterdir())


def test_assessment_time_is_not_ignored():
    payload = json.loads(INPUT.read_bytes())
    payload["assessment_time"] = "2027-01-02T00:00:00Z"
    for evidence in payload["evidence"].values():
        evidence["valid_until"] = "2027-12-31T23:59:59Z"
    assert AssessmentService().assess_execution(payload).decision == "ELIGIBLE"


def test_old_eligibility_publishers_are_retired():
    assert importlib.util.find_spec("kg_mnp.pipeline") is None
    assert not (ROOT / "scripts/showcase_demo.py").exists()
    assert not hasattr(assessment_service, "write_assessment_artifacts")
    for name in ("assess_dict", "assess_file", "assess_execution", "run_what_if"):
        parameters = inspect.signature(getattr(AssessmentService, name)).parameters
        assert not {"persist_artifacts", "artifact_dir", "write_html"} & parameters.keys()
