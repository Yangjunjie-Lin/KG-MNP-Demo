from __future__ import annotations

import socket
import threading
import time

import httpx
import uvicorn

from kg_mnp.api.app import create_app
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import ServiceConfiguration


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def test_real_http_port_exposes_authenticated_service(tmp_path):
    port = _free_port()
    service = ApplicationService(ServiceConfiguration(workspace_root=tmp_path, port=port))
    token, _ = service.tokens.create(
        principal_id="http-test",
        principal_type="HUMAN",
        permissions={"project:read", "project:write"},
        project_ids={"*"},
        created_by="test",
    )
    config = uvicorn.Config(create_app(service), host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        response = None
        while time.monotonic() < deadline:
            try:
                response = httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=1)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.05)
        assert response is not None and response.status_code == 200
        assert httpx.get(f"http://127.0.0.1:{port}/api/v1/health", timeout=2).status_code == 401
        response = httpx.get(f"http://127.0.0.1:{port}/api/v1/projects", headers={"Authorization": f"Bearer {token}"}, timeout=2)
        assert response.status_code == 200
        assert response.json() == {"projects": []}
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive()
