from __future__ import annotations

from fastapi.testclient import TestClient

from kg_mnp_demo.diagnostics.runtime import create_diagnostics_app

from ._helpers import snapshot
from .test_deterministic_diagnostics import requirement
from kg_mnp_demo.diagnostics import reconstruct_diagnostics


def test_runtime_is_read_only_and_escapes_text() -> None:
    package = reconstruct_diagnostics(snapshot(requirements=[requirement()], facts=[]))
    client = TestClient(create_diagnostics_app(package))
    response = client.get("/diagnostics/api/status")
    assert response.status_code == 200
    assert response.json()["status"] == "DIAGNOSTICS_READY"
    assert "Content-Security-Policy" in response.headers
    assert client.post("/diagnostics/api/status").status_code == 405
    assert client.get("/diagnostics/api/issues?focus_node=%2Fetc%2Fpasswd").status_code == 200
