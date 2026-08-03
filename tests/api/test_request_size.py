"""Request body size limit tests — must never skip."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

from kg_mnp_demo.api.app import create_app
from kg_mnp_demo.api.dependencies import AppState
from kg_mnp_demo.api.middleware.request_size import RequestSizeLimitMiddleware
from kg_mnp_demo.storage import AssessmentRepository, ArtifactRepository, Database

ROOT = Path(__file__).resolve().parents[2]


def _client(tmp_path: Path, monkeypatch, max_bytes: int = 200) -> TestClient:
    monkeypatch.setenv("KG_MNP_MAX_REQUEST_BYTES", str(max_bytes))
    state = AppState(
        db=Database(tmp_path / "db.sqlite3"),
        artifacts=ArtifactRepository(tmp_path / "exec"),
    )
    state.repository = AssessmentRepository(state.db)
    return TestClient(create_app(state))


def test_content_length_over_limit_returns_413(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, max_bytes=200)
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
    body = json.dumps({"payload": payload, "persist": False}).encode("utf-8")
    assert len(body) > 200
    resp = client.post(
        "/api/v1/assessments",
        content=body,
        headers={"content-type": "application/json", "content-length": str(len(body))},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "REQUEST_TOO_LARGE"
    assert "traceback" not in resp.text.lower()


def test_normal_case03_passes_under_default_limit(tmp_path, monkeypatch):
    monkeypatch.delenv("KG_MNP_MAX_REQUEST_BYTES", raising=False)
    state = AppState(
        db=Database(tmp_path / "db.sqlite3"),
        artifacts=ArtifactRepository(tmp_path / "exec"),
    )
    state.repository = AssessmentRepository(state.db)
    client = TestClient(create_app(state))
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
    resp = client.post("/api/v1/assessments", json={"payload": payload, "persist": False})
    assert resp.status_code == 200
    assert resp.json()["decision"] == "BLOCKED"


@pytest.mark.asyncio
async def test_streaming_body_without_content_length_enforced():
    """ASGI-level: reject when accumulated body exceeds max without Content-Length."""

    async def app(scope, receive, send):  # pragma: no cover - wrapped
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = RequestSizeLimitMiddleware(app, max_bytes=200)

    chunks = [b"a" * 150, b"b" * 150]
    sent = {"i": 0}

    async def receive():
        i = sent["i"]
        if i < len(chunks):
            body = chunks[i]
            sent["i"] += 1
            return {
                "type": "http.request",
                "body": body,
                "more_body": i < len(chunks) - 1,
            }
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/assessments",
        "raw_path": b"/api/v1/assessments",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    messages = []

    async def send(message):
        messages.append(message)

    await middleware(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    assert start["status"] == 413
