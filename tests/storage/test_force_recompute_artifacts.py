"""force_recompute must replace DB row and remove the prior artifact directory."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.persist import find_orphan_artifacts, persist_assessment
from kg_mnp_demo.storage import (
    AssessmentRepository,
    ArtifactRepository,
    Database,
    SaveExecutionOutcome,
)

ROOT = Path(__file__).resolve().parents[2]


def test_force_recompute_replaces_record_and_artifact(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    repo = AssessmentRepository(db)
    arts = ArtifactRepository(tmp_path / "executions")
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))

    first = persist_assessment(
        payload=payload,
        repository=repo,
        artifacts=arts,
        persist=True,
        force_recompute=False,
    )
    first_id = first["execution_id"]
    assert len(list((tmp_path / "executions").iterdir())) == 1
    assert len(repo.list_executions()) == 1

    second = persist_assessment(
        payload=payload,
        repository=repo,
        artifacts=arts,
        persist=True,
        force_recompute=True,
    )
    second_id = second["execution_id"]
    assert second_id != first_id
    assert len(repo.list_executions()) == 1
    dirs = [p.name for p in (tmp_path / "executions").iterdir() if p.is_dir()]
    assert dirs == [second_id]
    assert not (tmp_path / "executions" / first_id).exists()
    orphans = find_orphan_artifacts(repo, arts)
    assert orphans["orphan_directories"] == []


def test_force_recompute_db_failure_keeps_old_artifact(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    repo = AssessmentRepository(db)
    arts = ArtifactRepository(tmp_path / "executions")
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))

    first = persist_assessment(
        payload=payload,
        repository=repo,
        artifacts=arts,
        persist=True,
        force_recompute=False,
    )
    first_id = first["execution_id"]

    with patch.object(
        repo,
        "save_execution_outcome",
        side_effect=ApplicationError(ErrorCode.STORAGE_ERROR, message="fail"),
    ):
        with pytest.raises(ApplicationError):
            persist_assessment(
                payload=payload,
                repository=repo,
                artifacts=arts,
                persist=True,
                force_recompute=True,
            )

    assert (tmp_path / "executions" / first_id).is_dir()
    assert repo.get_execution(first_id)["execution_id"] == first_id
    # New orphan dirs should not remain
    dirs = [p.name for p in (tmp_path / "executions").iterdir() if p.is_dir()]
    assert dirs == [first_id]


def test_force_recompute_trigger_failure_cleans_new_artifact(tmp_path):
    """A real SQLite INSERT failure preserves both old DB and old artifacts."""
    db = Database(tmp_path / "db.sqlite3")
    repo = AssessmentRepository(db)
    arts = ArtifactRepository(tmp_path / "executions")
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))

    first = persist_assessment(
        payload=payload,
        repository=repo,
        artifacts=arts,
        persist=True,
        force_recompute=False,
    )
    first_id = first["execution_id"]
    db.connection.execute(
        f"""
        CREATE TRIGGER fail_replacement_insert
        BEFORE INSERT ON executions
        WHEN NEW.execution_id <> '{first_id}'
        BEGIN
            SELECT RAISE(ABORT, 'injected replacement failure');
        END;
        """
    )
    db.commit()

    with pytest.raises(ApplicationError) as exc_info:
        persist_assessment(
            payload=payload,
            repository=repo,
            artifacts=arts,
            persist=True,
            force_recompute=True,
        )

    assert exc_info.value.code == ErrorCode.STORAGE_ERROR
    assert repo.get_execution(first_id)["execution_id"] == first_id
    dirs = [p.name for p in arts.root.iterdir() if p.is_dir()]
    assert dirs == [first_id]
    db.connection.execute("DROP TRIGGER fail_replacement_insert")
    db.commit()


def test_artifact_cleanup_failure_does_not_mask_database_error(tmp_path, caplog):
    db = Database(tmp_path / "db.sqlite3")
    repo = AssessmentRepository(db)
    arts = ArtifactRepository(tmp_path / "executions")
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))

    first = persist_assessment(
        payload=payload,
        repository=repo,
        artifacts=arts,
        persist=True,
        force_recompute=False,
    )
    first_id = first["execution_id"]
    storage_error = ApplicationError(ErrorCode.STORAGE_ERROR, message="injected DB failure")

    with patch.object(repo, "save_execution_outcome", side_effect=storage_error):
        with patch.object(
            arts,
            "cleanup_execution_dir",
            side_effect=RuntimeError("injected cleanup failure"),
        ):
            with pytest.raises(ApplicationError) as exc_info:
                persist_assessment(
                    payload=payload,
                    repository=repo,
                    artifacts=arts,
                    persist=True,
                    force_recompute=True,
                )

    assert exc_info.value is storage_error
    assert exc_info.value.code == ErrorCode.STORAGE_ERROR
    assert (tmp_path / "executions" / first_id).is_dir()
    assert any("Artifact cleanup failed" in record.message for record in caplog.records)


def test_concurrent_force_recompute_leaves_only_retained_artifact(tmp_path):
    """Concurrent force_recompute must leave DB and disk consistent (no orphans)."""
    db = Database(tmp_path / "concurrent-force-artifacts.sqlite3")
    repo = AssessmentRepository(db)
    arts = ArtifactRepository(tmp_path / "executions")
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))

    seed = persist_assessment(
        payload=payload,
        repository=repo,
        artifacts=arts,
        persist=True,
        force_recompute=False,
    )
    assert seed["execution_id"]
    assert len(repo.list_executions()) == 1

    workers = 8
    barrier = threading.Barrier(workers)

    def force_once(_: int) -> str:
        barrier.wait(timeout=30)
        result = persist_assessment(
            payload=payload,
            repository=repo,
            artifacts=arts,
            persist=True,
            force_recompute=True,
        )
        return result["execution_id"]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        returned = list(pool.map(force_once, range(workers)))

    assert len(returned) == workers
    retained = repo.list_executions()
    assert len(retained) == 1
    final_id = retained[0]["execution_id"]
    final_dir = retained[0]["artifact_directory"]
    assert final_id in returned
    assert final_dir == final_id

    dirs = sorted(p.name for p in arts.root.iterdir() if p.is_dir())
    assert dirs == [final_id]

    orphans = find_orphan_artifacts(repo, arts)
    assert orphans["orphan_directories"] == []
    assert orphans["missing_directories"] == []
    assert db.connection.in_transaction is False
    # Connection remains usable after the concurrent storm.
    assert repo.get_execution(final_id)["execution_id"] == final_id
    probe = repo.save_execution_outcome(
        execution_id="post-concurrent-probe",
        case_id="PROBE",
        assessment_time="2026-01-01T00:00:00Z",
        input_payload={"probe": True},
        result={
            "schema_version": "1.0",
            "execution_id": "post-concurrent-probe",
            "case_id": "PROBE",
            "assessment_time": "2026-01-01T00:00:00Z",
            "decision": "ELIGIBLE",
            "publication": {"publishable": True, "status": "PUBLISHABLE"},
        },
    )
    assert isinstance(probe, SaveExecutionOutcome)
    assert probe.inserted is True


def test_concurrent_force_recompute_cleanup_failure_is_reported_without_corrupting_db(
    tmp_path, caplog
):
    """Cleanup failures after commit must not corrupt the retained DB row."""
    db = Database(tmp_path / "cleanup-fail-force.sqlite3")
    repo = AssessmentRepository(db)
    arts = ArtifactRepository(tmp_path / "executions")
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))

    first = persist_assessment(
        payload=payload,
        repository=repo,
        artifacts=arts,
        persist=True,
        force_recompute=False,
    )
    first_id = first["execution_id"]

    workers = 8
    barrier = threading.Barrier(workers)
    real_cleanup = arts.cleanup_execution_dir

    def flaky_cleanup(execution_id: str) -> None:
        if execution_id == first_id:
            raise RuntimeError("injected cleanup failure for seed")
        return real_cleanup(execution_id)

    def force_once(_: int) -> dict:
        barrier.wait(timeout=30)
        return persist_assessment(
            payload=payload,
            repository=repo,
            artifacts=arts,
            persist=True,
            force_recompute=True,
        )

    with patch.object(arts, "cleanup_execution_dir", side_effect=flaky_cleanup):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(force_once, range(workers)))

    assert len(results) == workers
    retained = repo.list_executions()
    assert len(retained) == 1
    final_id = retained[0]["execution_id"]
    assert final_id != first_id
    assert (arts.root / final_id).is_dir()
    assert db.connection.in_transaction is False
    assert repo.get_execution(final_id)["case_id"] == retained[0]["case_id"]
    assert any("Artifact cleanup failed" in record.message for record in caplog.records)
