from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from kg_mnp_demo.api.app import create_app
from kg_mnp_demo.api.dependencies import AppState
from kg_mnp_demo.storage import AssessmentRepository, ArtifactRepository, Database, default_db_path

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tmp_state(tmp_path):
    db = Database(tmp_path / "api.sqlite3")
    return AppState(
        db=db,
        repository=AssessmentRepository(db),
        artifacts=ArtifactRepository(tmp_path / "executions"),
    )


@pytest.fixture
def client(tmp_state):
    app = create_app(tmp_state)
    with TestClient(app) as c:
        yield c


def test_app_uses_injected_test_state(tmp_path, tmp_state):
    default_before = default_db_path()
    count_before = 0
    if default_before.exists():
        import sqlite3

        conn = sqlite3.connect(str(default_before))
        try:
            count_before = conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
        except sqlite3.Error:
            count_before = 0
        finally:
            conn.close()

    app = create_app(tmp_state)
    assert app.state.kg_mnp is tmp_state
    with TestClient(app) as client:
        payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
        resp = client.post("/api/v1/assessments", json={"payload": payload, "persist": True})
        assert resp.status_code == 200
        assert tmp_state.repository.list_executions()

    if default_before.exists():
        import sqlite3

        conn = sqlite3.connect(str(default_before))
        try:
            count_after = conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
        except sqlite3.Error:
            count_after = count_before
        finally:
            conn.close()
        assert count_after == count_before


def test_two_apps_are_isolated(tmp_path):
    a = AppState(
        db=Database(tmp_path / "a.sqlite3"),
        artifacts=ArtifactRepository(tmp_path / "a_art"),
    )
    a.repository = AssessmentRepository(a.db)
    b = AppState(
        db=Database(tmp_path / "b.sqlite3"),
        artifacts=ArtifactRepository(tmp_path / "b_art"),
    )
    b.repository = AssessmentRepository(b.db)
    app_a = create_app(a)
    app_b = create_app(b)
    assert app_a.state.kg_mnp is a
    assert app_b.state.kg_mnp is b
    assert app_a.state.kg_mnp is not app_b.state.kg_mnp


def test_lifespan_does_not_overwrite_injected_state(tmp_state):
    app = create_app(tmp_state)
    with TestClient(app) as client:
        assert client.app.state.kg_mnp is tmp_state
        assert client.get("/api/v1/health").status_code == 200
