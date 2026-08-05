"""CASE-06 historical vs current rule-version assessments must be real executions."""

from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.application.assessment_service import AssessmentService

ROOT = Path(__file__).resolve().parents[2]


def _canonical_time(value: object) -> str:
    return str(value or "").replace("+00:00", "Z")


def _assert_execution_consistency(result: dict) -> None:
    decision = result.get("decision")
    rules = result.get("rule_results") or []
    reasons = result.get("blocking_reasons") or []
    assessment_time = _canonical_time(result.get("assessment_time"))

    assert decision != "BLOCKED" or reasons
    assert decision != "ELIGIBLE" or not reasons

    failed_rule_ids = {
        row.get("rule_id") for row in rules if row.get("status") == "FAIL"
    }
    for reason in reasons:
        if rule_id := reason.get("rule_id"):
            assert rule_id in failed_rule_ids

    for evidence in result.get("evidence") or []:
        generated_at = _canonical_time(evidence.get("generated_at"))
        assert not generated_at or not assessment_time or generated_at <= assessment_time

    for rule in rules:
        selected_at = _canonical_time(rule.get("selected_for_assessment_time"))
        if selected_at and assessment_time:
            assert selected_at == assessment_time
        effective_from = _canonical_time(rule.get("effective_from"))
        effective_to = _canonical_time(rule.get("effective_to"))
        assert not effective_from or not assessment_time or effective_from <= assessment_time
        assert not effective_to or not assessment_time or effective_to >= assessment_time


def _rule(result: dict, rule_id: str) -> dict:
    for row in result.get("rule_results") or []:
        if row.get("rule_id") == rule_id:
            return row
    raise AssertionError(f"missing rule {rule_id}")


def test_case06_history_and_current_are_real_rule_executions():
    svc = AssessmentService()
    historical = svc.assess_dict(
        json.loads((ROOT / "inputs" / "case06_history.json").read_text(encoding="utf-8"))
    )
    current = svc.assess_dict(
        json.loads((ROOT / "inputs" / "case06.json").read_text(encoding="utf-8"))
    )

    _assert_execution_consistency(historical)
    _assert_execution_consistency(current)

    assert historical["decision"] == "ELIGIBLE"
    assert current["decision"] == "BLOCKED"
    assert historical["blocking_reasons"] == []
    assert any(
        r["reason_code"] == "PORTING_INTERVAL_TOO_SHORT"
        for r in current["blocking_reasons"]
    )

    hist_rule = _rule(historical, "MNP-ELIG-005")
    cur_rule = _rule(current, "MNP-ELIG-005")
    assert hist_rule["version"] == "1.0"
    assert hist_rule["status"] == "PASS"
    assert cur_rule["version"] == "1.1"
    assert cur_rule["status"] == "FAIL"

    assert historical["assessment_time"].startswith("2026-05-15")
    assert current["assessment_time"].startswith("2026-07-01")

    for ev in historical["evidence"]:
        gen = (ev.get("generated_at") or "").replace("+00:00", "Z")
        assert gen <= "2026-05-15T12:00:00Z"
