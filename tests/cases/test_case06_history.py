"""CASE-06 historical vs current rule-version assessments must be real executions."""

from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.application.assessment_service import AssessmentService
from kg_mnp_demo.application.persist import assert_execution_consistency

ROOT = Path(__file__).resolve().parents[2]


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

    assert_execution_consistency(historical)
    assert_execution_consistency(current)

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
