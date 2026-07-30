"""Eligibility rule engine tests for six cases."""

from kg_mnp_demo.evaluator import evaluate_case
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph
from kg_mnp_demo.rule_engine import evaluate_rules, load_rules, summarize_decision


def _eval(case_id: str, use_updated: bool = True):
    g = load_case_graph(case_id)
    apply_owlrl(g)
    return evaluate_case(g, case_id, use_updated_rules=use_updated)


def test_case_01_eligible():
    result = _eval("CASE-01")
    assert result["decision"] == "ELIGIBLE"
    assert result["blocking_reasons"] == []


def test_case_02_billing_block_only():
    result = _eval("CASE-02")
    assert result["decision"] == "BLOCKED"
    codes = [b["reason_code"] for b in result["blocking_reasons"]]
    assert codes == ["OUTSTANDING_BALANCE"]
    reason = result["blocking_reasons"][0]
    assert reason["rule_id"] == "MNP-ELIG-003"
    assert reason["regulatory_clause"] == "REG-MNP-CLAUSE-03"
    assert reason["action_code"] == "SETTLE_OUTSTANDING_FEES"
    assert reason["evidence"]["status"] == "VALID"
    assert reason["evidence"]["source_system"] == "BILLING"


def test_case_03_contract_block_full_trace():
    result = _eval("CASE-03")
    assert result["decision"] == "BLOCKED"
    reason = result["blocking_reasons"][0]
    assert reason["reason_code"] == "ACTIVE_CONTRACT_RESTRICTION"
    assert reason["rule_version"] == "1.0"
    assert reason["evidence"]["evidence_id"]
    assert reason["regulatory_clause"]
    assert reason["action_code"]
    assert result["trace_paths"]


def test_case_04_two_independent_blocks():
    result = _eval("CASE-04")
    assert result["decision"] == "BLOCKED"
    codes = sorted(b["reason_code"] for b in result["blocking_reasons"])
    assert codes == ["ACTIVE_CONTRACT_RESTRICTION", "OUTSTANDING_BALANCE"]
    assert len(result["trace_paths"]) >= 2


def test_case_05_manual_review_expired_evidence():
    result = _eval("CASE-05")
    assert result["decision"] == "MANUAL_REVIEW"
    codes = [b["reason_code"] for b in result["blocking_reasons"]]
    assert "MISSING_OR_EXPIRED_EVIDENCE" in codes


def test_case_06_updated_rule_blocks_port_interval():
    result = _eval("CASE-06", use_updated=True)
    assert result["decision"] == "BLOCKED"
    assert any(
        b["reason_code"] == "PORTING_INTERVAL_TOO_SHORT"
        for b in result["blocking_reasons"]
    )


def test_case_06_old_rules_would_pass():
    g = load_case_graph("CASE-06")
    outcomes = evaluate_rules(g, "CASE-06", use_updated_rules=False)
    assert summarize_decision(outcomes) == "ELIGIBLE"


def test_rules_metadata_complete():
    for rule in load_rules(include_updates=False):
        for key in [
            "rule_id",
            "version",
            "effective_from",
            "inputs",
            "decision_when_pass",
            "decision_when_fail",
            "missing_evidence_action",
            "reason_code",
            "action_code",
            "regulatory_clause",
        ]:
            assert key in rule


def test_deterministic_repeat():
    a = _eval("CASE-04")
    b = _eval("CASE-04")
    assert a["decision"] == b["decision"]
    assert [x["reason_code"] for x in a["blocking_reasons"]] == [
        x["reason_code"] for x in b["blocking_reasons"]
    ]
