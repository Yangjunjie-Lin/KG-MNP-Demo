"""BlockingReason per-reason integrity SHACL tests."""

from __future__ import annotations

from rdflib.namespace import RDF

from kg_mnp_demo.evaluator import evaluate_case
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph
from kg_mnp_demo.namespaces import DATA, MNP
from kg_mnp_demo.validator import validate_graph


def _assessed(case_id: str):
    g = load_case_graph(case_id)
    apply_owlrl(g)
    evaluate_case(g, case_id, validate=False)
    return g


def _case04_reasons(graph):
    reasons = sorted(
        (
            r
            for r in graph.subjects(RDF.type, MNP.BlockingReason)
            if "CASE-04" in str(r)
        ),
        key=str,
    )
    assert len(reasons) == 2
    return reasons


def test_case03_blocking_reason_conforms():
    g = _assessed("CASE-03")
    assert validate_graph(g).conforms


def test_case04_both_reasons_complete():
    g = _assessed("CASE-04")
    assert validate_graph(g).conforms
    reasons = _case04_reasons(g)
    for reason in reasons:
        assert list(g.objects(reason, MNP.recommendsAction))
        assert list(g.objects(reason, MNP.supportedByEvidence))
        assert list(g.objects(reason, MNP.triggeredByRule))
        assert list(g.objects(reason, MNP.triggeredByRuleVersion))
        assert list(g.objects(reason, MNP.citesClause))


def test_each_case04_reason_requires_its_own_action():
    g = _assessed("CASE-04")
    reasons = _case04_reasons(g)
    for reason in reasons:
        g2 = g.__class__()
        for t in g:
            g2.add(t)
        for triple in list(g2.triples((reason, MNP.recommendsAction, None))):
            g2.remove(triple)
        result = validate_graph(g2)
        assert not result.conforms, str(reason)
        assert "处理动作" in result.text or "recommendsAction" in result.text


def test_case04_missing_evidence_fails():
    g = _assessed("CASE-04")
    reason = _case04_reasons(g)[0]
    for triple in list(g.triples((reason, MNP.supportedByEvidence, None))):
        g.remove(triple)
    assert not validate_graph(g).conforms


def test_case04_missing_rule_fails():
    g = _assessed("CASE-04")
    reason = _case04_reasons(g)[0]
    for triple in list(g.triples((reason, MNP.triggeredByRule, None))):
        g.remove(triple)
    assert not validate_graph(g).conforms


def test_case04_missing_rule_version_fails():
    g = _assessed("CASE-04")
    reason = _case04_reasons(g)[1]
    for triple in list(g.triples((reason, MNP.triggeredByRuleVersion, None))):
        g.remove(triple)
    assert not validate_graph(g).conforms


def test_case04_missing_clause_fails():
    g = _assessed("CASE-04")
    reason = _case04_reasons(g)[1]
    for triple in list(g.triples((reason, MNP.citesClause, None))):
        g.remove(triple)
    assert not validate_graph(g).conforms


def test_foreign_evidence_on_reason_fails():
    from rdflib import Literal

    g = _assessed("CASE-03")
    reason = next(g.subjects(RDF.type, MNP.BlockingReason))
    foreign = DATA["ForeignEv-For-Reason"]
    g.add((foreign, RDF.type, MNP.EvidenceRecord))
    g.add((foreign, MNP.evidenceType, Literal("CONTRACT_STATUS")))
    g.add((foreign, MNP.evidenceStatus, Literal("VALID")))
    g.add((foreign, MNP.evidenceGeneratedAt, Literal("2026-06-20T10:15:00Z")))
    g.add((foreign, MNP.hasSourceSystem, DATA["SYS-CONTRACT"]))
    for triple in list(g.triples((reason, MNP.supportedByEvidence, None))):
        g.remove(triple)
    g.add((reason, MNP.supportedByEvidence, foreign))
    result = validate_graph(g)
    assert not result.conforms
    assert "不是所属资格评估实际使用的证据" in result.text


def test_foreign_rule_version_on_reason_fails():
    g = _assessed("CASE-03")
    reason = next(g.subjects(RDF.type, MNP.BlockingReason))
    # Point to a version the assessment did not use for this failure path
    foreign_rv = DATA["RuleVersion-MNP-ELIG-005-1-1"]
    for triple in list(g.triples((reason, MNP.triggeredByRuleVersion, None))):
        g.remove(triple)
    g.add((reason, MNP.triggeredByRuleVersion, foreign_rv))
    # Ensure assessment does not also use that version for the reason's assessment
    # (assessment may still use 1.1 for porting rule — remove from assessment)
    assessment = DATA["Assessment-CASE-03"]
    for triple in list(g.triples((assessment, MNP.usesRuleVersion, foreign_rv))):
        g.remove(triple)
    result = validate_graph(g)
    assert not result.conforms
    assert "规则版本" in result.text


def test_unrelated_clause_on_reason_fails():
    g = _assessed("CASE-03")
    reason = next(g.subjects(RDF.type, MNP.BlockingReason))
    # Cite a clause not operationalized by the triggered rule
    wrong_clause = DATA["Clause-01"]
    for triple in list(g.triples((reason, MNP.citesClause, None))):
        g.remove(triple)
    g.add((reason, MNP.citesClause, wrong_clause))
    result = validate_graph(g)
    assert not result.conforms
    assert "监管条款" in result.text


def test_case01_no_blocking_reason_still_conforms():
    g = _assessed("CASE-01")
    assert validate_graph(g).conforms
    assert not list(g.subjects(RDF.type, MNP.BlockingReason))
