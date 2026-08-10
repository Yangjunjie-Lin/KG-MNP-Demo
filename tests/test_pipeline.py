"""End-to-end JSON → RDF pipeline tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


from kg_mnp_demo.pipeline import run_pipeline
from kg_mnp_demo.trace_graph import edges_exist_in_graph

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_OUTPUTS = [
    "normalized_input.json",
    "input_graph.ttl",
    "input_validation.json",
    "inference.json",
    "evaluation.json",
    "assessment_graph.ttl",
    "assessment_validation.json",
    "trace_subgraph.json",
    "report.html",
]


def test_json_case03_blocked(tmp_path):
    result = run_pipeline(
        ROOT / "inputs" / "case03.json",
        tmp_path / "case03",
        write_html=True,
    )
    assert result["exit_code"] == 0
    assert result["decision"] == "BLOCKED"
    reasons = result["evaluation"]["blocking_reasons"]
    assert reasons[0]["reason_code"] == "ACTIVE_CONTRACT_RESTRICTION"
    assert reasons[0]["rule_id"] == "MNP-ELIG-004"
    assert reasons[0]["rule_version"] == "1.0"
    assert reasons[0]["regulatory_clause"] == "REG-MNP-CLAUSE-04"
    assert reasons[0]["action_code"] == "WAIT_OR_TERMINATE_CONTRACT"
    assert result["input_validation"]["status"] == "PASSED"
    assert result["assessment_validation"]["status"] == "PASSED"
    assert result["evaluation"]["publishable"] is True


def test_trace_contains_real_entities(tmp_path):
    result = run_pipeline(
        ROOT / "inputs" / "case03.json",
        tmp_path / "case03",
        write_html=False,
    )
    sub = result["trace_subgraph"]
    preds = {e["predicate"] for e in sub["edges"]}
    assert "usesEvidence" in preds
    assert "evaluatedByRule" in preds
    assert "usesRuleVersion" in preds
    assert "operationalizesClause" in preds
    assert "recommendsAction" in preds
    missing = edges_exist_in_graph(result["assessment_graph"], sub)
    assert missing == []


def test_output_files_complete(tmp_path):
    out = tmp_path / "case03"
    run_pipeline(ROOT / "inputs" / "case03.json", out, write_html=True)
    for name in REQUIRED_OUTPUTS:
        assert (out / name).exists(), name


def test_repeatable_pipeline(tmp_path):
    a = run_pipeline(ROOT / "inputs" / "case03.json", tmp_path / "a", write_html=False)
    b = run_pipeline(ROOT / "inputs" / "case03.json", tmp_path / "b", write_html=False)
    assert a["decision"] == b["decision"]
    assert a["evaluation"]["blocking_reasons"] == b["evaluation"]["blocking_reasons"]
    assert a["trace_subgraph"]["edges"] == b["trace_subgraph"]["edges"]
    # Instance TTL (pre-OWL blank nodes) must be identical across runs
    ttl_a = (tmp_path / "a" / "input_graph.ttl").read_text(encoding="utf-8")
    ttl_b = (tmp_path / "b" / "input_graph.ttl").read_text(encoding="utf-8")
    assert ttl_a == ttl_b


def test_assessment_time_affects_contract(tmp_path):
    # After contract end, with still-valid evidence windows → ELIGIBLE
    import json
    from kg_mnp_demo.input_adapter import normalize_case_input
    from kg_mnp_demo.pipeline import merge_reference_graph
    from kg_mnp_demo.rdf_builder import build_case_graph
    from kg_mnp_demo.evaluator import evaluate_case
    from kg_mnp_demo.inference import apply_owlrl
    from kg_mnp_demo.validator import validate_graph

    data = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
    data["assessment_time"] = "2027-01-02T00:00:00Z"
    # Extend evidence validity so only the contract check changes
    for key in data["evidence"]:
        data["evidence"][key]["valid_until"] = "2027-12-31T23:59:59Z"
    normalized = normalize_case_input(data)
    g = merge_reference_graph(build_case_graph(normalized))
    assert validate_graph(g).conforms
    apply_owlrl(g)
    result = evaluate_case(
        g,
        "CASE-03",
        assessment_time=datetime(2027, 1, 2, tzinfo=timezone.utc),
        validate=False,
    )
    assert result["decision"] == "ELIGIBLE"


def test_invalid_json_does_not_publish(tmp_path):
    result = run_pipeline(
        ROOT / "inputs" / "invalid_missing_source.json",
        tmp_path / "bad",
        write_html=False,
    )
    assert result["exit_code"] == 1
    assert result["decision"] is None
    assert result["publishable"] is False
