"""Tests for real RDF assessment subgraph tracing."""

from __future__ import annotations

from rdflib import URIRef

from kg_mnp_demo.evaluator import evaluate_case, materialize_assessment
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph
from kg_mnp_demo.namespaces import MNP
from kg_mnp_demo.trace import affected_assessments
from kg_mnp_demo.trace_graph import build_assessment_subgraph, edges_exist_in_graph
from kg_mnp_demo.validator import validate_graph


def _assessed(case_id: str):
    g = load_case_graph(case_id)
    apply_owlrl(g)
    evaluate_case(g, case_id, validate=False)
    return g, build_assessment_subgraph(g, case_id)


def test_subgraph_edges_exist_in_rdf():
    g, sub = _assessed("CASE-03")
    missing = edges_exist_in_graph(g, sub)
    assert missing == []


def test_no_fabricated_linear_edges():
    from rdflib.namespace import RDF

    g, sub = _assessed("CASE-03")
    forbidden = []
    for e in sub["edges"]:
        src = URIRef(e["source"])
        types = {str(t).rsplit("#", 1)[-1] for t in g.objects(src, RDF.type)}
        pred = e["predicate"]
        if ("EvidenceRecord" in types or "SystemObservation" in types) and pred in {
            "triggeredByRuleVersion",
            "operationalizesClause",
            "producesDecision",
        }:
            forbidden.append(e)
        if "RegulatoryClause" in types and pred == "producesDecision":
            forbidden.append(e)
    assert forbidden == []


def test_case03_subgraph_complete():
    g, sub = _assessed("CASE-03")
    preds = {e["predicate"] for e in sub["edges"]}
    for required in [
        "hasEligibilityAssessment",
        "usesEvidence",
        "evaluatedByRule",
        "usesRuleVersion",
        "producesDecision",
        "producesBlockingReason",
        "operationalizesClause",
        "recommendsAction",
        "dependsOn",
    ]:
        assert required in preds, required
    types = {n["type"] for n in sub["nodes"]}
    assert "BlockingReason" in types
    assert "EligibilityRule" in types
    assert "RegulatoryClause" in types


def test_case04_two_blocking_reason_branches():
    g, sub = _assessed("CASE-04")
    reason_edges = [
        e for e in sub["edges"] if e["predicate"] == "producesBlockingReason"
    ]
    assert len(reason_edges) == 2
    targets = {e["target_local"] for e in reason_edges}
    assert len(targets) == 2


def test_case06_affected_assessments_deduped():
    g = load_case_graph("CASE-06")
    apply_owlrl(g)
    materialize_assessment(g, "CASE-06", validate=False)
    rows = affected_assessments(g)
    hist = [r for r in rows if (r.get("assessmentId") or "") == "ASSESS-CASE-06-HIST"]
    assert len(hist) == 1


def test_dual_shacl_in_showcase_pipeline():
    from pathlib import Path
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "showcase_demo.py"
    spec = importlib.util.spec_from_file_location("showcase_demo", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    primary = mod.evaluate_pipeline("CASE-03")
    assert primary["input_validation"]["status"] == "PASSED"
    assert primary["assessment_validation"]["status"] == "PASSED"
    assert primary["evaluation"]["publishable"] is True


def test_assessment_missing_action_fails_result_validation():
    from rdflib.namespace import RDF

    g = load_case_graph("CASE-03")
    apply_owlrl(g)
    evaluate_case(g, "CASE-03", validate=False)
    for reason in list(g.subjects(RDF.type, MNP.BlockingReason)):
        for triple in list(g.triples((reason, MNP.recommendsAction, None))):
            g.remove(triple)
    result = validate_graph(g)
    assert not result.conforms
