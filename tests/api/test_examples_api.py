from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from kg_mnp_demo.api.app import create_app
from kg_mnp_demo.api.dependencies import AppState
from kg_mnp_demo.namespaces import CASE_FILES, EXAMPLE_META
from kg_mnp_demo.storage import AssessmentRepository, ArtifactRepository, Database

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(tmp_path):
    db = Database(tmp_path / "ex.sqlite3")
    state = AppState(
        db=db,
        repository=AssessmentRepository(db),
        artifacts=ArtifactRepository(tmp_path / "exec"),
    )
    with TestClient(create_app(state)) as c:
        yield c


EXPECTED = {cid: meta["expected_decision"] for cid, meta in EXAMPLE_META.items()}


@pytest.mark.parametrize("case_id", sorted(CASE_FILES.keys()))
def test_example_get_and_run(client, case_id):
    detail = client.get(f"/api/v1/examples/{case_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["runnable"] is True
    assert body["input"] is not None
    assert body["expected_decision"] == EXPECTED[case_id]

    run = client.post(f"/api/v1/examples/{case_id}/run")
    assert run.status_code == 200, run.text
    assert run.json()["decision"] == EXPECTED[case_id]


def test_examples_list_all_runnable(client):
    resp = client.get("/api/v1/examples")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 9
    assert all(i["runnable"] for i in items)
