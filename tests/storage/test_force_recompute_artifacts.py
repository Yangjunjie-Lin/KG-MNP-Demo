"""force_recompute must replace DB row and remove the prior artifact directory."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.persist import find_orphan_artifacts, persist_assessment
from kg_mnp_demo.storage import AssessmentRepository, ArtifactRepository, Database

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
        "save_execution",
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

    with patch.object(repo, "save_execution", side_effect=storage_error):
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
