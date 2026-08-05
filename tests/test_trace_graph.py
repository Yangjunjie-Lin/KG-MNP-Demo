"""Tests for SPARQL-backed assessment subgraph tracing."""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import URIRef
from rdflib.namespace import RDF

from kg_mnp_demo.evaluator import evaluate_case, materialize_assessment
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph, query_path
from kg_mnp_demo.namespaces import DATA, MNP
from kg_mnp_demo.trace import affected_assessments
from kg_mnp_demo.trace_graph import (
    SUBGRAPH_QUERY_FILE,
    TraceSubgraphIntegrityError,
    build_assessment_subgraph,
    edges_exist_in_graph,
    format_subgraph_tree,
    render_subgraph_html,
)
from kg_mnp_demo.validator import validate_graph


def _assessed(case_id: str):
    g = load_case_graph(case_id)
    apply_owlrl(g)
    evaluate_case(g, case_id, validate=False)
    return g, build_assessment_subgraph(g, case_id)


def test_uses_assessment_subgraph_rq():
    g, sub = _assessed("CASE-03")
    assert sub["query_file"] == SUBGRAPH_QUERY_FILE
    assert Path(query_path(SUBGRAPH_QUERY_FILE)).exists()
    assert sub["edges"]


def test_subgraph_edges_exist_in_rdf():
    g, sub = _assessed("CASE-03")
    assert edges_exist_in_graph(g, sub) == []


def test_edges_have_predicate_iri():
    _, sub = _assessed("CASE-03")
    for edge in sub["edges"]:
        assert edge["predicate_iri"].startswith("https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#")
        assert edge["predicate"] == edge["predicate_iri"].rsplit("#", 1)[-1]


def test_nodes_cover_edge_endpoints():
    _, sub = _assessed("CASE-03")
    ids = {n["id"] for n in sub["nodes"]}
    for edge in sub["edges"]:
        assert edge["source"] in ids
        assert edge["target"] in ids


def test_no_duplicate_edges():
    _, sub = _assessed("CASE-03")
    keys = [(e["source"], e["predicate_iri"], e["target"]) for e in sub["edges"]]
    assert len(keys) == len(set(keys))


def test_no_fabricated_linear_edges():
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
    _, sub = _assessed("CASE-03")
    preds = {e["predicate"] for e in sub["edges"]}
    for required in [
        "hasEligibilityAssessment",
        "usesEvidence",
        "evaluatedByRule",
        "usesRuleVersion",
        "producesDecision",
        "hasBlockingReason",
        "operationalizesClause",
        "recommendsAction",
    ]:
        assert required in preds, required


def test_case04_two_blocking_reason_branches():
    _, sub = _assessed("CASE-04")
    reason_edges = [
        e for e in sub["edges"] if e["predicate"] == "hasBlockingReason"
    ]
    assert len(reason_edges) == 2


def test_case06_affected_assessments_deduped():
    g = load_case_graph("CASE-06")
    apply_owlrl(g)
    materialize_assessment(g, "CASE-06", validate=False)
    rows = affected_assessments(g)
    hist = [r for r in rows if (r.get("assessmentId") or "") == "ASSESS-CASE-06-HIST"]
    assert len(hist) == 1


def test_special_case_id_safe():
    g = load_case_graph("CASE-03")
    apply_owlrl(g)
    evaluate_case(g, "CASE-03", validate=False)
    # Value is passed via initBindings (not string-spliced into SPARQL).
    sub = build_assessment_subgraph(g, "CASE-99-no-such\"case")
    assert sub["edges"] == []


def test_missing_rq_fails(monkeypatch):
    from kg_mnp_demo import trace_graph as tg

    monkeypatch.setattr(
        tg,
        "query_path",
        lambda name: Path("/nonexistent/assessment_subgraph.rq"),
    )
    g = load_case_graph("CASE-03")
    with pytest.raises(FileNotFoundError):
        tg.build_assessment_subgraph(g, "CASE-03")


def test_rq_change_affects_output(monkeypatch, tmp_path):
    from kg_mnp_demo import trace_graph as tg

    g, baseline = _assessed("CASE-03")
    stub = tmp_path / "assessment_subgraph.rq"
    # Intentionally omit hasEligibilityAssessment so results diverge from baseline.
    stub.write_text(
        """
PREFIX mnp: <https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#>
SELECT DISTINCT ?subject ?predicate ?object WHERE {
  ?case mnp:caseIdentifier ?caseId ;
        mnp:hasEligibilityAssessment ?assessment .
  FILTER(STR(?caseId) = STR(?requestedCaseId))
  ?assessment mnp:producesDecision ?object .
  BIND(?assessment AS ?subject)
  BIND(mnp:producesDecision AS ?predicate)
  FILTER(isIRI(?subject) && isIRI(?predicate) && isIRI(?object))
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(tg, "query_path", lambda name: stub)
    altered = tg.build_assessment_subgraph(g, "CASE-03")
    assert altered["edges"]
    assert {e["predicate"] for e in altered["edges"]} == {"producesDecision"}
    assert {e["predicate"] for e in baseline["edges"]} != {"producesDecision"}


def test_html_and_tree_use_same_edges():
    _, sub = _assessed("CASE-03")
    tree = format_subgraph_tree(sub)
    html = render_subgraph_html(sub)
    assert "hasBlockingReason" in tree
    assert "hasBlockingReason" in html
    assert "usesEvidence" in tree
    assert "usesEvidence" in html
    for edge in sub["edges"]:
        # Display layers consume edge predicates, not invent them
        assert edge["predicate"]


def test_repeatable_subgraph():
    a = _assessed("CASE-03")[1]
    b = _assessed("CASE-03")[1]
    assert a["edges"] == b["edges"]
    assert a["nodes"] == b["nodes"]


def test_dual_shacl_in_showcase_pipeline():
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
    g = load_case_graph("CASE-03")
    apply_owlrl(g)
    evaluate_case(g, "CASE-03", validate=False)
    for reason in list(g.subjects(RDF.type, MNP.BlockingReason)):
        for triple in list(g.triples((reason, MNP.recommendsAction, None))):
            g.remove(triple)
    result = validate_graph(g)
    assert not result.conforms
