"""Legacy eligibility use-case behavior retained after the Stage 01 cleanup."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kg_mnp_demo.application.assessment_service import AssessmentService
from kg_mnp_demo.application.query_service import QueryService
from kg_mnp_demo.namespaces import CASE_FILES

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def service():
    return AssessmentService()


def test_case07_eligible_process_blocked(service):
    payload = json.loads((ROOT / "inputs" / "case07.json").read_text(encoding="utf-8"))
    result = service.assess_dict(payload)
    assert result["decision"] == "ELIGIBLE"
    assert result["process"]["can_advance"] is False
    codes = [b["code"] for b in result["process"]["blocking_reasons"]]
    assert "AUTHORIZATION_CODE_EXPIRED" in codes
    assert result["process"]["authorization_code"]["status"] == "EXPIRED"


def test_case08_termination_pending(service):
    payload = json.loads((ROOT / "inputs" / "case08.json").read_text(encoding="utf-8"))
    result = service.assess_dict(payload)
    assert result["decision"] == "BLOCKED"
    proc_codes = [b["code"] for b in result["process"]["blocking_reasons"]]
    assert (
        "TERMINATION_NOT_EFFECTIVE" in proc_codes
        or "ELIGIBILITY_NOT_PASSED" in proc_codes
    )


def test_case09_identity_conflict(service):
    payload = json.loads((ROOT / "inputs" / "case09.json").read_text(encoding="utf-8"))
    result = service.assess_dict(payload)
    assert result["decision"] == "BLOCKED"
    assert result["blocking_reasons"][0]["reason_code"] == "REAL_NAME_MISMATCH"


def test_all_cq_execute():
    qs = QueryService()
    for q in qs.list_questions():
        example = q["example_case"]
        if example not in CASE_FILES:
            continue
        result = qs.execute(q["id"], case_id=example)
        assert result["status"] == "ANSWERED"
        assert result["question_id"] == q["id"]
        json.dumps(result)


def test_case04_two_blocking_reasons():
    from kg_mnp_demo.loader import load_case_graph
    from kg_mnp_demo.inference import apply_owlrl
    from kg_mnp_demo.evaluator import evaluate_case

    g = load_case_graph("CASE-04")
    apply_owlrl(g)
    result = evaluate_case(g, "CASE-04", use_updated_rules=True, validate=False)
    assert len(result["blocking_reasons"]) >= 2
