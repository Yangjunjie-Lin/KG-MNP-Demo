"""CORS behaviour against real HTTP responses."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

from kg_mnp_demo.api.app import create_app
from kg_mnp_demo.api.dependencies import AppState
from kg_mnp_demo.storage import AssessmentRepository, ArtifactRepository, Database


def test_cors_allows_configured_origin(tmp_path, monkeypatch):
    monkeypatch.setenv("KG_MNP_CORS_ORIGINS", "http://localhost:3000")
    state = AppState(
        db=Database(tmp_path / "db.sqlite3"),
        artifacts=ArtifactRepository(tmp_path / "exec"),
    )
    state.repository = AssessmentRepository(state.db)
    client = TestClient(create_app(state))
    resp = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_rejects_untrusted_origin(tmp_path, monkeypatch):
    monkeypatch.setenv("KG_MNP_CORS_ORIGINS", "http://localhost:3000")
    state = AppState(
        db=Database(tmp_path / "db.sqlite3"),
        artifacts=ArtifactRepository(tmp_path / "exec"),
    )
    state.repository = AssessmentRepository(state.db)
    client = TestClient(create_app(state))
    resp = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") != "https://untrusted.example"
