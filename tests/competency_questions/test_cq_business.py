"""CQ-01..CQ-15 business result assertions (not only ANSWERED)."""

from __future__ import annotations

from kg_mnp_demo.application.query_service import QueryService
from kg_mnp_demo.evaluator import materialize_assessment
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph
from kg_mnp_demo.validator import validate_graph

# CQ | Case | Expected key fields
# CQ-01 CASE-01 decision=ELIGIBLE
# CQ-02 CASE-04 two blocking reason codes
# CQ-03 CASE-03 contract evidence IRI
# CQ-04 CASE-03 CONTRACT source + generatedAt
# CQ-05 CASE-06 MNP-ELIG-005 versions 1.0/1.1
# CQ-06 CASE-03 REG-MNP-CLAUSE-04
# CQ-07 CASE-03 WAIT_OR_TERMINATE_CONTRACT
# CQ-08 CASE-07 AUTHORIZATION_CODE_REQUEST
# CQ-09 CASE-07 AUTHORIZATION_CODE_EXPIRED
# CQ-10 CASE-07 authStatus=EXPIRED
# CQ-11 CASE-01 Svc-Mobile-Basic subscription
# CQ-12 CASE-03 contractStatus=ACTIVE
# CQ-13 CASE-02 billing evidence present
# CQ-14 CASE-04 >=2 reasons and actions
# CQ-15 CASE-06 historical assessment, oldVersion=1.0, requiresReassessment=true


def _graph(case_id: str):
    g = load_case_graph(case_id)
    assert validate_graph(g).conforms
    apply_owlrl(g)
    materialize_assessment(g, case_id, use_updated_rules=True, validate=False)
    return g


def test_cq01_case01_eligible():
    result = QueryService().execute("CQ-01", case_id="CASE-01", graph=_graph("CASE-01"))
    assert any(r.get("decision") == "ELIGIBLE" for r in result["rows"])


def test_cq02_case04_two_reasons():
    result = QueryService().execute("CQ-02", case_id="CASE-04", graph=_graph("CASE-04"))
    codes = sorted(r.get("reasonCode") for r in result["rows"] if r.get("reasonCode"))
    assert len(codes) >= 2
    assert "OUTSTANDING_BALANCE" in codes
    assert "ACTIVE_CONTRACT_RESTRICTION" in codes


def test_cq03_case03_contract_evidence():
    result = QueryService().execute("CQ-03", case_id="CASE-03", graph=_graph("CASE-03"))
    assert result["rows"]
    assert any(r.get("evidence") for r in result["rows"])


def test_cq04_case03_contract_source():
    result = QueryService().execute("CQ-04", case_id="CASE-03", graph=_graph("CASE-03"))
    assert any(r.get("sourceSystem") == "CONTRACT" for r in result["rows"])
    assert any(r.get("generatedAt") for r in result["rows"])


def test_cq05_case06_versions():
    result = QueryService().execute("CQ-05", case_id="CASE-06", graph=_graph("CASE-06"))
    versions = {(r.get("ruleId"), r.get("ruleVersion")) for r in result["rows"]}
    assert ("MNP-ELIG-005", "1.0") in versions or ("MNP-ELIG-005", "1.1") in versions


def test_cq06_case03_clause():
    result = QueryService().execute("CQ-06", case_id="CASE-03", graph=_graph("CASE-03"))
    assert any(r.get("clauseId") == "REG-MNP-CLAUSE-04" for r in result["rows"])


def test_cq07_case03_action():
    result = QueryService().execute("CQ-07", case_id="CASE-03", graph=_graph("CASE-03"))
    assert any(r.get("actionCode") == "WAIT_OR_TERMINATE_CONTRACT" for r in result["rows"])


def test_cq08_case07_step():
    result = QueryService().execute("CQ-08", case_id="CASE-07", graph=_graph("CASE-07"))
    assert result["rows"]
    assert any(
        r.get("stepCode") == "AUTHORIZATION_CODE_REQUEST" for r in result["rows"]
    )


def test_cq09_case07_process_event():
    result = QueryService().execute("CQ-09", case_id="CASE-07", graph=_graph("CASE-07"))
    assert result["rows"]
    assert any(
        r.get("eventTypeCode") == "AUTHORIZATION_CODE_EXPIRED" for r in result["rows"]
    )


def test_cq10_case07_auth_expired():
    result = QueryService().execute("CQ-10", case_id="CASE-07", graph=_graph("CASE-07"))
    assert any(r.get("authStatus") == "EXPIRED" for r in result["rows"])


def test_cq11_case01_service():
    result = QueryService().execute("CQ-11", case_id="CASE-01", graph=_graph("CASE-01"))
    assert result["rows"]
    assert any(
        "Svc-Mobile-Basic" in str(r.get("service") or "") for r in result["rows"]
    )
    assert any(r.get("subscriptionStatus") == "ACTIVE" for r in result["rows"])


def test_cq12_case03_contract_status():
    result = QueryService().execute("CQ-12", case_id="CASE-03", graph=_graph("CASE-03"))
    assert any(r.get("contractStatus") == "ACTIVE" for r in result["rows"])


def test_cq13_case02_billing():
    result = QueryService().execute("CQ-13", case_id="CASE-02", graph=_graph("CASE-02"))
    assert result["rows"]
    assert any(r.get("evidence") for r in result["rows"])


def test_cq14_case04_actions():
    result = QueryService().execute("CQ-14", case_id="CASE-04", graph=_graph("CASE-04"))
    reasons = {r.get("reasonCode") for r in result["rows"]}
    actions = {r.get("actionCode") for r in result["rows"]}
    assert len(reasons) >= 2
    assert len([a for a in actions if a]) >= 2


def test_cq15_case06_reassessment():
    result = QueryService().execute("CQ-15", case_id="CASE-06", graph=_graph("CASE-06"))
    assert result["rows"]
    assert any("Assessment-CASE-06-HIST" in str(r.get("assessment") or "") for r in result["rows"])
    assert any(r.get("oldVersion") == "1.0" for r in result["rows"])
    assert any(
        str(r.get("requiresReassessment")).lower() in {"true", "1"}
        for r in result["rows"]
    )
