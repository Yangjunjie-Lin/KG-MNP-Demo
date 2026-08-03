"""Essential API, storage, CQ, process and presentation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kg_mnp_demo.application.assessment_service import AssessmentService
from kg_mnp_demo.application.process_service import evaluate_process_state
from kg_mnp_demo.application.query_service import QueryService
from kg_mnp_demo.namespaces import CASE_FILES
from kg_mnp_demo.storage import AssessmentRepository, Database, compute_input_hash

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
    assert "TERMINATION_NOT_EFFECTIVE" in proc_codes or "ELIGIBILITY_NOT_PASSED" in proc_codes


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


def test_storage_idempotent(tmp_path):
    db = Database(tmp_path / "t.sqlite3")
    repo = AssessmentRepository(db)
    payload = {"case_id": "CASE-03", "x": 1}
    result = {
        "schema_version": "1.0",
        "execution_id": "e1",
        "case_id": "CASE-03",
        "assessment_time": "2026-07-01T00:00:00Z",
        "decision": "BLOCKED",
        "publication": {"publishable": True, "status": "PUBLISHABLE"},
        "blocking_reasons": [{"reason_code": "A"}],
        "rule_results": [],
    }
    a = repo.save_execution(
        execution_id="e1",
        case_id="CASE-03",
        assessment_time="2026-07-01T00:00:00Z",
        input_payload=payload,
        result=result,
    )
    b = repo.save_execution(
        execution_id="e2",
        case_id="CASE-03",
        assessment_time="2026-07-01T00:00:00Z",
        input_payload=payload,
        result={**result, "execution_id": "e2"},
    )
    assert a["execution_id"] == b["execution_id"] == "e1"
    c = repo.save_execution(
        execution_id="e3",
        case_id="CASE-03",
        assessment_time="2026-07-01T00:00:00Z",
        input_payload=payload,
        result={**result, "execution_id": "e3"},
        force_recompute=True,
    )
    assert c["execution_id"] == "e3"


def test_storage_compare(tmp_path):
    db = Database(tmp_path / "c.sqlite3")
    repo = AssessmentRepository(db)
    left = {
        "schema_version": "1.0",
        "execution_id": "L",
        "case_id": "CASE-03",
        "assessment_time": "2026-07-01T00:00:00Z",
        "decision": "BLOCKED",
        "publication": {"publishable": True, "status": "PUBLISHABLE"},
        "blocking_reasons": [{"reason_code": "A"}],
        "rule_results": [{"rule_id": "R", "version": "1.0"}],
    }
    right = {
        **left,
        "execution_id": "R",
        "decision": "ELIGIBLE",
        "blocking_reasons": [],
        "rule_results": [{"rule_id": "R", "version": "1.1"}],
    }
    repo.save_execution(
        execution_id="L",
        case_id="CASE-03",
        assessment_time="2026-07-01T00:00:00Z",
        input_payload={"a": 1},
        result=left,
        force_recompute=True,
    )
    repo.save_execution(
        execution_id="R",
        case_id="CASE-03",
        assessment_time="2026-07-02T00:00:00Z",
        input_payload={"a": 2},
        result=right,
        force_recompute=True,
    )
    cmp = repo.compare_executions("L", "R")
    assert cmp["decision_changed"] is True
    assert "A" in cmp["removed_blocking_reasons"]
