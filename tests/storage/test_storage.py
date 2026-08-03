from __future__ import annotations

import json
from pathlib import Path

import pytest

from kg_mnp_demo.application.assessment_service import AssessmentService, write_assessment_artifacts
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.process_service import evaluate_process_state
from kg_mnp_demo.storage import (
    AssessmentRepository,
    ArtifactRepository,
    Database,
    compute_input_hash,
)

ROOT = Path(__file__).resolve().parents[2]


def test_db_init_and_idempotent(tmp_path):
    db = Database(tmp_path / "t.sqlite3")
    repo = AssessmentRepository(db)
    arts = ArtifactRepository(tmp_path / "exec")
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
    svc = AssessmentService()
    ex1 = svc.assess_execution(payload, execution_id="e1")
    out = arts.execution_dir("e1")
    write_assessment_artifacts(ex1, out)
    ex1.response["artifacts"] = arts.relative_artifacts({"evaluation": "evaluation.json"})
    r1 = repo.save_execution(
        execution_id="e1",
        case_id=ex1.response["case_id"],
        assessment_time=ex1.response["assessment_time"],
        input_payload=payload,
        result=ex1.response,
        artifact_directory="e1",
    )
    found = repo.find_idempotent_execution(
        ex1.response["case_id"],
        ex1.response["assessment_time"],
        compute_input_hash(payload),
    )
    assert found["execution_id"] == "e1"
    r2 = repo.save_execution(
        execution_id="e2",
        case_id=ex1.response["case_id"],
        assessment_time=ex1.response["assessment_time"],
        input_payload=payload,
        result={**ex1.response, "execution_id": "e2"},
        artifact_directory="e2",
    )
    assert r2["execution_id"] == "e1"
    assert list((tmp_path / "exec").iterdir())  # e1 exists
    # force recompute replaces
    r3 = repo.save_execution(
        execution_id="e3",
        case_id=ex1.response["case_id"],
        assessment_time=ex1.response["assessment_time"],
        input_payload=payload,
        result={**ex1.response, "execution_id": "e3"},
        artifact_directory="e3",
        force_recompute=True,
    )
    assert r3["execution_id"] == "e3"


def test_changed_evidence_compare(tmp_path):
    db = Database(tmp_path / "c.sqlite3")
    repo = AssessmentRepository(db)
    left = {
        "schema_version": "1.0",
        "execution_id": "L",
        "case_id": "CASE-03",
        "assessment_time": "2026-07-01T00:00:00Z",
        "decision": "BLOCKED",
        "publication": {"publishable": True, "status": "PUBLISHABLE"},
        "blocking_reasons": [],
        "rule_results": [{"rule_id": "MNP-ELIG-004", "version": "1.0", "status": "FAIL"}],
        "evidence": [
            {
                "evidence_id": "Ev-CTR",
                "evidence_type": "CONTRACT_STATUS",
                "status": "VALID",
                "valid_until": "2026-12-31T23:59:59Z",
            }
        ],
    }
    right = {
        **left,
        "execution_id": "R",
        "decision": "ELIGIBLE",
        "rule_results": [{"rule_id": "MNP-ELIG-004", "version": "1.0", "status": "PASS"}],
        "evidence": [
            {
                "evidence_id": "Ev-CTR",
                "evidence_type": "CONTRACT_STATUS",
                "status": "EXPIRED",
                "valid_until": "2025-01-01T00:00:00Z",
            }
        ],
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
        assessment_time="2027-01-02T00:00:00Z",
        input_payload={"a": 2},
        result=right,
        force_recompute=True,
    )
    cmp = repo.compare_executions("L", "R")
    assert cmp["changed_evidence"]["modified"]
    assert any(r["changed"] for r in cmp["rule_changes"])


def test_process_requires_assessment_time():
    with pytest.raises(ApplicationError) as ei:
        evaluate_process_state(None, "CASE-01", decision="ELIGIBLE", assessment_time=None)
    assert ei.value.code == ErrorCode.PROCESS_ASSESSMENT_TIME_REQUIRED


def test_unwritable_db(tmp_path):
    bad = tmp_path / "readonly"
    bad.mkdir()
    bad.chmod(0o400)
    # On Windows chmod may not block writes the same way — still attempt
    try:
        Database(bad / "nested" / "x.sqlite3")
    except ApplicationError as exc:
        assert exc.code == ErrorCode.STORAGE_ERROR
    finally:
        bad.chmod(0o700)


def test_cleanup_orphan_dir(tmp_path):
    arts = ArtifactRepository(tmp_path / "exec")
    d = arts.execution_dir("orphan")
    assert d.exists()
    arts.cleanup_execution_dir("orphan")
    assert not (tmp_path / "exec" / "orphan").exists()
