"""Former relay attack cases now target the one authenticated resource API."""
import importlib.util

import pytest
from fastapi.testclient import TestClient

from kg_mnp.api.app import create_app
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import ServiceConfiguration


@pytest.fixture
def application(tmp_path):
    return create_app(ApplicationService(ServiceConfiguration(str(tmp_path / "service"))))


@pytest.mark.parametrize("path", [
    "http://evil.example/", "https://evil.example/", "//evil.example/",
    "/@evil.example", "/%68%74%74%70%3A%2F%2Fevil.example",
    "/%2568%2574%2574%2570%253A%252F%252Fevil.example", "/api/v1/../../secret",
    "/api/v1/entity?iri=http://evil.example", "/repositories/attacker", "\\\\evil.example\\share",
])
def test_absolute_encoded_and_non_allowlisted_targets_are_blocked(application, path, monkeypatch):
    import socket

    def no_network(*args, **kwargs):
        raise AssertionError("request target must never trigger an upstream connection")

    async def raw_target(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "path": path, "raw_path": path.encode("ascii")}
        await application(scope, receive, send)

    with TestClient(raw_target) as client:
        monkeypatch.setattr(socket, "create_connection", no_network)
        response = client.get("/probe")
    assert response.status_code in {400, 404, 410}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "CONNECT", "OPTIONS"])
def test_mutating_and_tunneling_methods_are_blocked(application, method):
    with TestClient(application) as client:
        assert client.request(method, "/healthz").status_code == 405
        assert client.get("/healthz").json() == {"status": "ALIVE"}


def test_query_parameter_allowlist_is_exact(application):
    from kg_mnp.services.requests import ObjectRequest

    valid = {"package_id": "urn:kg-mnp:ontology-package:" + "a" * 64,
             "instance_iri": "urn:test", "limit": 10, "offset": 0}
    assert ObjectRequest.model_validate(valid).instance_iri == "urn:test"
    with TestClient(application) as client:
        response = client.post("/api/v1/projects/untrusted/objects/query",
                               json={**valid, "target": "http://evil.example"})
    assert response.status_code == 422


@pytest.mark.parametrize("upstream", [
    "https://127.0.0.1:8081", "http://localhost:8081", "http://0.0.0.0:8081",
    "http://127.0.0.1:8081/api", "http://evil.example:8081", "http://user@127.0.0.1:8081",
    "https://example.invalid", "http://localhost:8080", "http://127.0.0.1:8081", "http://127.0.0.1:8080/remote",
])
def test_client_cannot_choose_any_upstream(application, upstream):
    with TestClient(application) as client:
        response = client.post("/api/v1/projects/untrusted/objects/query",
                               json={"package_id": "urn:kg-mnp:ontology-package:" + "a" * 64, "instance_iri": "urn:test", "upstream": upstream})
    assert response.status_code == 422


def test_old_relay_runtime_is_not_importable():
    assert importlib.util.find_spec("kg_mnp.workbench.relay") is None
