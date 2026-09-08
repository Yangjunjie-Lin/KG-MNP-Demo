"""Wire-level assurances migrated from the retired unauthenticated runtimes.

These exercise the current app and real credential/project stores, not an old
controlled HTTP fixture. Business authority tests remain in services/lifecycle.
"""
import json

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from rdflib import Literal

from kg_mnp.api.app import create_app
from kg_mnp.integrations.local_rdf import LocalRDFQueryAdapter
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import ServiceConfiguration

ATTACKS = (
    "<script>alert(1)</script>", "<img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>", "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>", "&#x6a;avascript:alert(1)",
    "%3Cscript%3Ealert(1)%3C/script%3E", '\"</div><script>alert(1)</script>',
    "urn:datatype:<script>alert(1)</script>", "en-<img-src-x>",
    "urn:source:<svg-onload-alert>",
)


@pytest.fixture
def wire(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path / "service")))
    token, _ = service.tokens.create(principal_id="wire-human", principal_type="HUMAN",
        permissions={"*"}, project_ids=set(), created_by="synthetic-test")
    with TestClient(create_app(service), base_url="https://testserver", raise_server_exceptions=False) as client:
        response = client.post("/api/v1/session", headers={"Authorization": f"Bearer {token}", "Origin": "https://testserver"})
        assert response.status_code == 200
        client.headers.update({"Origin": "https://testserver", "X-CSRF-Token": response.json()["csrf_token"]})
        yield client


@pytest.mark.parametrize("body", [
    b'{"name":"first","name":"second","domain_pack":"minimal","domain_pack_version":"0.1.0"}',
    b'{"name":"first","nested":{"key":1,"key":2}}',
    b'{"name":NaN}', b'{"name":Infinity}', b'{"name":1e999}',
    b'{"name":"\xff"}', b'{"name":', b'[' * 2000 + b']' * 2000,
], ids=["duplicate", "nested-duplicate", "nan", "infinity", "overflow", "invalid-utf8", "incomplete", "too-deep"])
def test_ambiguous_or_invalid_json_is_rejected_before_authority_dispatch(wire, body):
    response = wire.post("/api/v1/projects", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REQUEST_JSON_INVALID"
    assert wire.get("/api/v1/projects").json()["projects"] == []


@pytest.mark.parametrize("content_type", ["text/plain", "text/html", "application/x-www-form-urlencoded", ""])
def test_non_json_mutation_content_type_cannot_reach_dispatch(wire, content_type):
    body = json.dumps({"name": "blocked", "domain_pack": "minimal", "domain_pack_version": "0.1.0"})
    response = wire.post("/api/v1/projects", content=body, headers={"Content-Type": content_type})
    assert response.status_code == 415
    assert wire.get("/api/v1/projects").json()["projects"] == []


@pytest.mark.parametrize("field", ["workspace_path", "authority_package_path", "artifact_path", "file_path", "authority_snapshot", "principal", "reviewer_roles"])
def test_client_cannot_inject_paths_authority_or_roles(wire, field):
    body = {"name": "blocked", "domain_pack": "minimal", "domain_pack_version": "0.1.0", field: "../../escape"}
    response = wire.post("/api/v1/projects", json=body)
    assert response.status_code == 422
    assert wire.get("/api/v1/projects").json()["projects"] == []


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_read_request_bodies_are_not_interpreted_as_hidden_commands(wire, method):
    response = wire.request(method, "/healthz", content=b"unexpected")
    assert response.status_code == 405


@pytest.mark.parametrize("method", ["CONNECT", "TRACE", "PUT", "PATCH", "DELETE"])
def test_forbidden_health_methods_do_not_mutate(wire, method):
    assert wire.request(method, "/healthz").status_code == 405


@pytest.mark.parametrize("attack", ATTACKS)
def test_untrusted_text_roundtrips_as_json_never_active_content(wire, attack):
    term = LocalRDFQueryAdapter._term(Literal(attack))
    rendered = JSONResponse(term)
    assert json.loads(rendered.body)["value"] == attack
    result = wire.post("/api/v1/projects", json={"name": attack, "domain_pack": "minimal", "domain_pack_version": "0.1.0"})
    # Project display names additionally reject path-like characters. That
    # restriction must not be loosened merely to construct an XSS test input.
    if any(char in attack for char in "\\/:"):
        assert result.status_code == 422
        assert wire.get("/api/v1/projects").json()["projects"] == []
        return
    assert result.status_code == 200
    response = wire.get("/api/v1/projects")
    assert response.headers["content-type"].startswith("application/json")
    assert attack in response.text or attack in json.dumps(response.json(), ensure_ascii=False)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


def test_no_proxy_or_arbitrary_sparql_endpoint(wire):
    for path in ("/proxy/http://evil.example", "/sparql", "/api/v1/sparql"):
        assert wire.get(path).status_code == 404
    assert wire.get("/healthz").json() == {"status": "ALIVE"}


@pytest.mark.parametrize("prefix", ["workbench", "diagnostics", "governance"])
def test_retired_runtime_urls_have_no_read_or_write_authority(wire, prefix):
    for method in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"):
        result = wire.request(method, f"/{prefix}/api/status")
        assert result.status_code == 410
        assert result.headers["cache-control"] == "no-store"
