from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
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
    repo.save_execution(
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


def test_latest_case_execution_uses_assessment_time(tmp_path):
    db = Database(tmp_path / "latest.sqlite3")
    repo = AssessmentRepository(db)
    current = {
        "schema_version": "1.0",
        "execution_id": "current",
        "case_id": "CASE-06",
        "assessment_time": "2026-07-01T00:00:00Z",
        "decision": "BLOCKED",
        "publication": {"publishable": True, "status": "PUBLISHABLE"},
    }
    historical = {
        **current,
        "execution_id": "historical",
        "assessment_time": "2026-05-15T00:00:00Z",
        "decision": "ELIGIBLE",
    }

    repo.save_execution(
        execution_id="current",
        case_id="CASE-06",
        assessment_time=current["assessment_time"],
        input_payload={"version": "current"},
        result=current,
        force_recompute=True,
    )
    # Historical imports may be persisted later than the current assessment.
    repo.save_execution(
        execution_id="historical",
        case_id="CASE-06",
        assessment_time=historical["assessment_time"],
        input_payload={"version": "historical"},
        result=historical,
        force_recompute=True,
    )

    latest = repo.get_latest_case_execution("CASE-06")
    history = repo.list_case_history("CASE-06")
    latest_counts = repo.latest_case_decision_counts()

    assert latest["execution_id"] == "current"
    assert [item["execution_id"] for item in history] == ["current", "historical"]
    assert latest_counts["blocked"] == 1
    assert latest_counts["eligible"] == 0


def test_latest_case_execution_returns_none_without_history(tmp_path):
    db = Database(tmp_path / "empty-latest.sqlite3")
    repo = AssessmentRepository(db)

    assert repo.get_latest_case_execution("CASE-03") is None


def test_parallel_history_reads_share_connection_safely(tmp_path):
    db = Database(tmp_path / "parallel.sqlite3")
    repo = AssessmentRepository(db)
    result = {
        "schema_version": "1.0",
        "execution_id": "parallel",
        "case_id": "CASE-03",
        "assessment_time": "2026-07-01T00:00:00Z",
        "decision": "BLOCKED",
        "publication": {"publishable": True, "status": "PUBLISHABLE"},
    }
    repo.save_execution(
        execution_id="parallel",
        case_id="CASE-03",
        assessment_time=result["assessment_time"],
        input_payload={"case": "parallel"},
        result=result,
        force_recompute=True,
    )

    def read_history(_: int):
        return repo.list_case_history("CASE-03")

    with ThreadPoolExecutor(max_workers=12) as pool:
        histories = list(pool.map(read_history, range(200)))

    assert all(items[0]["execution_id"] == "parallel" for items in histories)


def test_process_requires_assessment_time():
    with pytest.raises(ApplicationError) as ei:
        evaluate_process_state(None, "CASE-01", decision="ELIGIBLE", assessment_time=None)
    assert ei.value.code == ErrorCode.PROCESS_ASSESSMENT_TIME_REQUIRED


def test_unwritable_db(tmp_path):
    not_a_directory = tmp_path / "not-a-directory"
    not_a_directory.write_text("file", encoding="utf-8")
    with pytest.raises(ApplicationError) as exc:
        Database(not_a_directory / "db.sqlite3")
    assert exc.value.code == ErrorCode.STORAGE_ERROR


def test_cleanup_orphan_dir(tmp_path):
    arts = ArtifactRepository(tmp_path / "exec")
    d = arts.execution_dir("orphan")
    assert d.exists()
    arts.cleanup_execution_dir("orphan")
    assert not (tmp_path / "exec" / "orphan").exists()


def test_force_recompute_insert_failure_rolls_back_delete(tmp_path):
    """A failed replacement must leave the prior idempotent row committed."""
    db = Database(tmp_path / "atomic.sqlite3")
    repo = AssessmentRepository(db)
    assessment_time = "2026-07-01T00:00:00Z"
    payload = {"case": "atomicity"}
    old_result = {
        "schema_version": "1.0",
        "execution_id": "old-execution",
        "case_id": "CASE-03",
        "assessment_time": assessment_time,
        "decision": "BLOCKED",
        "publication": {"publishable": True, "status": "PUBLISHABLE"},
    }
    repo.save_execution(
        execution_id="old-execution",
        case_id="CASE-03",
        assessment_time=assessment_time,
        input_payload=payload,
        result=old_result,
    )

    db.connection.execute(
        """
        CREATE TRIGGER fail_forced_insert
        BEFORE INSERT ON executions
        WHEN NEW.execution_id = 'forced-failure'
        BEGIN
            SELECT RAISE(ABORT, 'injected insert failure');
        END;
        """
    )
    db.commit()

    with pytest.raises(ApplicationError) as exc_info:
        repo.save_execution(
            execution_id="forced-failure",
            case_id="CASE-03",
            assessment_time=assessment_time,
            input_payload=payload,
            result={**old_result, "execution_id": "forced-failure"},
            force_recompute=True,
        )

    assert exc_info.value.code == ErrorCode.STORAGE_ERROR
    assert db.connection.in_transaction is False
    assert repo.get_execution("old-execution")["execution_id"] == "old-execution"
    assert repo.find_idempotent_execution(
        "CASE-03", assessment_time, compute_input_hash(payload)
    )["execution_id"] == "old-execution"
    assert db.fetchone(
        "SELECT execution_id FROM executions WHERE execution_id = ?",
        ("forced-failure",),
    ) is None

    # The connection remains usable after rollback and the trigger can be
    # removed before a successful replacement.
    db.connection.execute("DROP TRIGGER fail_forced_insert")
    db.commit()
    replacement = repo.save_execution(
        execution_id="new-execution",
        case_id="CASE-03",
        assessment_time=assessment_time,
        input_payload=payload,
        result={**old_result, "execution_id": "new-execution"},
        force_recompute=True,
    )
    assert replacement["execution_id"] == "new-execution"
    with pytest.raises(ApplicationError) as missing:
        repo.get_execution("old-execution")
    assert missing.value.code == ErrorCode.EXECUTION_NOT_FOUND
    assert db.fetchone(
        """
        SELECT COUNT(*) AS n FROM executions
        WHERE case_id = ? AND assessment_time = ? AND input_hash = ?
        """,
        ("CASE-03", assessment_time, compute_input_hash(payload)),
    )["n"] == 1


def test_transaction_rolls_back_and_nested_savepoint_isolated(tmp_path):
    db = Database(tmp_path / "transaction-context.sqlite3")
    db.execute("CREATE TABLE scratch (value INTEGER NOT NULL)")
    db.commit()

    with db.transaction(immediate=True) as conn:
        conn.execute("INSERT INTO scratch(value) VALUES (1)")
        with pytest.raises(RuntimeError):
            with db.transaction():
                conn.execute("INSERT INTO scratch(value) VALUES (2)")
                raise RuntimeError("rollback nested unit")
        assert conn.execute("SELECT COUNT(*) FROM scratch").fetchone()[0] == 1

    assert db.fetchone("SELECT COUNT(*) FROM scratch")[0] == 1
    with pytest.raises(ValueError):
        with db.transaction():
            db.execute("INSERT INTO scratch(value) VALUES (3)")
            raise ValueError("rollback outer unit")
    assert db.fetchone("SELECT COUNT(*) FROM scratch")[0] == 1
    assert db.connection.in_transaction is False


def test_concurrent_idempotent_writes_return_one_record(tmp_path):
    db = Database(tmp_path / "concurrent-idempotent.sqlite3")
    repo = AssessmentRepository(db)
    assessment_time = "2026-07-01T00:00:00Z"
    payload = {"case": "same-input"}

    def write(attempt: int) -> str:
        execution_id = f"ordinary-{attempt}"
        result = {
            "schema_version": "1.0",
            "execution_id": execution_id,
            "case_id": "CASE-03",
            "assessment_time": assessment_time,
            "decision": "BLOCKED",
            "publication": {"publishable": True, "status": "PUBLISHABLE"},
        }
        return repo.save_execution(
            execution_id=execution_id,
            case_id="CASE-03",
            assessment_time=assessment_time,
            input_payload=payload,
            result=result,
        )["execution_id"]

    with ThreadPoolExecutor(max_workers=16) as pool:
        returned = list(pool.map(write, range(64)))

    assert len(set(returned)) == 1
    assert len(repo.list_executions(case_id="CASE-03")) == 1
    assert db.fetchone("SELECT COUNT(*) AS n FROM executions")["n"] == 1
    assert db.connection.in_transaction is False


def test_concurrent_force_recompute_writes_are_serialized(tmp_path):
    db = Database(tmp_path / "concurrent-force.sqlite3")
    repo = AssessmentRepository(db)
    assessment_time = "2026-07-01T00:00:00Z"
    payload = {"case": "force-input"}
    base = {
        "schema_version": "1.0",
        "case_id": "CASE-03",
        "assessment_time": assessment_time,
        "decision": "BLOCKED",
        "publication": {"publishable": True, "status": "PUBLISHABLE"},
    }
    repo.save_execution(
        execution_id="force-seed",
        case_id="CASE-03",
        assessment_time=assessment_time,
        input_payload=payload,
        result={**base, "execution_id": "force-seed"},
    )

    def replace(attempt: int) -> str:
        execution_id = f"force-{attempt}"
        return repo.save_execution(
            execution_id=execution_id,
            case_id="CASE-03",
            assessment_time=assessment_time,
            input_payload=payload,
            result={**base, "execution_id": execution_id},
            force_recompute=True,
        )["execution_id"]

    expected_ids = {f"force-{i}" for i in range(32)}
    with ThreadPoolExecutor(max_workers=16) as pool:
        returned = list(pool.map(replace, range(32)))

    # Each force operation is a complete serialized replacement.  The return
    # value is the snapshot inserted by that call, while only the last row is
    # retained for the unique idempotency key.
    assert set(returned) == expected_ids
    retained = repo.list_executions(case_id="CASE-03")
    assert len(retained) == 1
    assert retained[0]["execution_id"] in expected_ids
    assert db.connection.in_transaction is False
    assert repo.get_execution(retained[0]["execution_id"])["case_id"] == "CASE-03"
