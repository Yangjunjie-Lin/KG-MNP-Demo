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
