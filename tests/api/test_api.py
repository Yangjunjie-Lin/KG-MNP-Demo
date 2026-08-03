from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from kg_mnp_demo.api.app import create_app
from kg_mnp_demo.api.dependencies import AppState, set_state
from kg_mnp_demo.storage import AssessmentRepository, ArtifactRepository, Database

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(tmp_path):
    db = Database(tmp_path / "api.sqlite3")
    state = AppState(
        db=db,
        repository=AssessmentRepository(db),
        artifacts=ArtifactRepository(tmp_path / "executions"),
    )
    set_state(state)
    app = create_app()
    # recreate lifespan state
    set_state(state)
    with TestClient(app) as c:
        yield c


def test_health_and_openapi(client):
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_post_case03(client):
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
    resp = client.post("/api/v1/assessments", json={"payload": payload, "persist": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "BLOCKED"
    execution_id = data["execution_id"]
    got = client.get(f"/api/v1/assessments/{execution_id}")
    assert got.status_code == 200
    trace = client.get(f"/api/v1/assessments/{execution_id}/trace")
    assert "nodes" in trace.json()
    hist = client.get("/api/v1/cases/CASE-03/history")
    assert hist.status_code == 200


def test_invalid_input(client):
    resp = client.post("/api/v1/assessments", json={"payload": {"case_id": "X"}, "persist": False})
    assert resp.status_code in (400, 422)
    body = resp.json()
    assert "error" in body or "detail" in body


def test_ontology_and_cq(client):
    assert client.get("/api/v1/ontology/summary").status_code == 200
    assert client.get("/api/v1/ontology/graph").status_code == 200
    resp = client.post(
        "/api/v1/competency-questions/CQ-02/execute",
        json={"case_id": "CASE-04"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ANSWERED"


def test_views_dashboard(client):
    resp = client.get("/api/v1/views/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ontology"]["competency_question_count"] == 15
    assert len(data["pipeline_steps"]) == 8


def test_not_found(client):
    resp = client.get("/api/v1/assessments/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "EXECUTION_NOT_FOUND"


def test_internal_error_no_traceback(client):
    # force via unknown CQ
    resp = client.get("/api/v1/competency-questions/CQ-999")
    assert resp.status_code == 404
    text = resp.text
    assert "Traceback" not in text
