"""SHACL validation tests."""

from kg_mnp_demo.loader import load_case_graph
from kg_mnp_demo.namespaces import MNP
from kg_mnp_demo.validator import validate_graph


def test_case_03_conforms():
    g = load_case_graph("CASE-03")
    result = validate_graph(g)
    assert result.conforms, result.text


def test_all_cases_conform():
    for case_id in [f"CASE-0{i}" for i in range(1, 7)]:
        g = load_case_graph(case_id)
        result = validate_graph(g)
        assert result.conforms, f"{case_id}: {result.text}"


def test_invalid_case_missing_applicant_fails():
    g = load_case_graph("CASE-01")
    for triple in list(g.triples((MNP["CASE-01"], MNP.requestedBy, None))):
        g.remove(triple)
    result = validate_graph(g)
    assert not result.conforms
    assert "申请人" in result.text or "requestedBy" in result.text


def test_active_contract_without_end_fails():
    g = load_case_graph("CASE-03")
    for triple in list(g.triples((MNP["Contract-03"], MNP.contractEndTime, None))):
        g.remove(triple)
    result = validate_graph(g)
    assert not result.conforms


def test_evidence_without_source_fails():
    g = load_case_graph("CASE-01")
    for triple in list(g.triples((MNP["Ev-01-ID"], MNP.hasSourceSystem, None))):
        g.remove(triple)
    result = validate_graph(g)
    assert not result.conforms
