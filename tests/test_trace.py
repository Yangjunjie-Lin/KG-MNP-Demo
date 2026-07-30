"""Traceability and rule-update impact tests."""

from kg_mnp_demo.evaluator import materialize_assessment
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph, load_ontology_graph
from kg_mnp_demo.trace import affected_assessments, blocking_reasons, decision_trace, source_alignment


def test_blocked_reason_trace_to_evidence_rule_clause_action():
    g = load_case_graph("CASE-03")
    apply_owlrl(g)
    materialize_assessment(g, "CASE-03")
    rows = blocking_reasons(g, "CASE-03")
    assert rows
    row = rows[0]
    assert row["reasonCode"] == "ACTIVE_CONTRACT_RESTRICTION"
    assert row["evidence"]
    assert row["ruleId"] == "MNP-ELIG-004"
    assert row["ruleVersion"]
    assert row["clauseId"] == "REG-MNP-CLAUSE-04"
    assert row["actionCode"] == "WAIT_OR_TERMINATE_CONTRACT"


def test_case_04_two_trace_chains():
    g = load_case_graph("CASE-04")
    apply_owlrl(g)
    materialize_assessment(g, "CASE-04")
    rows = blocking_reasons(g, "CASE-04")
    codes = sorted(r["reasonCode"] for r in rows)
    assert codes == ["ACTIVE_CONTRACT_RESTRICTION", "OUTSTANDING_BALANCE"]


def test_decision_trace_query_runs():
    g = load_case_graph("CASE-01")
    apply_owlrl(g)
    materialize_assessment(g, "CASE-01")
    rows = decision_trace(g, "CASE-01")
    assert rows
    assert any(r["decisionCode"] == "ELIGIBLE" for r in rows)


def test_affected_assessments_for_rule_update():
    g = load_case_graph("CASE-06")
    apply_owlrl(g)
    materialize_assessment(g, "CASE-06")
    rows = affected_assessments(g)
    assert rows
    assert any("ASSESS-CASE-06-HIST" in (r.get("assessmentId") or "") for r in rows)
    assert any(r.get("requiresReassessment") in ("true", "True", "1") or r.get("requiresReassessment") == "true" for r in rows) or any(
        "Reassess" in (r.get("assessment") or "") or r.get("oldVersion") == "1.0" for r in rows
    )


def test_source_alignment_query():
    g = load_ontology_graph(include_alignments=True)
    from kg_mnp_demo.loader import reference_paths, load_graph

    g2 = load_graph(reference_paths())
    for t in g2:
        g.add(t)
    rows = source_alignment(g)
    assert rows
    assert any(r.get("alignmentStatus") == "PARTIAL" for r in rows)
    assert any(r.get("mapApi") == "TMF629_CustomerManagement" for r in rows)
