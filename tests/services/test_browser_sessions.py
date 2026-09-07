from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kg_mnp.api.app import create_app
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import ServiceConfiguration


def test_opaque_cookie_session_csrf_logout_and_revoke(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    token, principal = service.tokens.create(principal_id="synthetic-browser", principal_type="HUMAN", permissions={"*"},
                                             project_ids=set(), created_by="test")
    with TestClient(create_app(service), base_url="https://testserver") as client:
        login = client.post("/api/v1/session", headers={"Authorization": f"Bearer {token}", "Origin": "https://testserver"})
        assert login.status_code == 200, login.text
        cookie = login.headers["set-cookie"]
        assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
        assert token not in cookie and token not in login.text
        assert client.get("/api/v1/me").json()["principal_id"] == principal.principal_id
        payload = {"name": "browser", "domain_pack": "minimal", "domain_pack_version": "0.1.0"}
        assert client.post("/api/v1/projects", json=payload).status_code == 403
        csrf = login.json()["csrf_token"]
        headers = {"Origin": "https://testserver", "X-CSRF-Token": csrf}
        assert client.post("/api/v1/projects", json=payload, headers=headers).status_code == 200
        assert client.post("/api/v1/projects", json=payload, headers={**headers, "Origin": "https://attacker.invalid"}).status_code == 403
        service.tokens.revoke(principal.token_id)
        assert client.get("/api/v1/me").status_code == 401


def test_session_logout_and_http_require_explicit_loopback_exception(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    token, _ = service.tokens.create(principal_id="human", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="test")
    with TestClient(create_app(service), base_url="http://127.0.0.1") as client:
        response = client.post("/api/v1/session", headers={"Authorization": f"Bearer {token}", "Origin": "http://127.0.0.1"})
        assert response.status_code == 403
    with TestClient(create_app(service), base_url="https://testserver") as client:
        login = client.post("/api/v1/session", headers={"Authorization": f"Bearer {token}", "Origin": "https://testserver"})
        assert login.status_code == 200
        cookie = client.cookies.get("kgmnp_session")
        assert client.post("/api/v1/session/logout", headers={"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrf_token"]}).status_code == 200
        assert client.get("/api/v1/me").status_code == 401
        client.cookies.set("kgmnp_session", cookie)
        assert client.get("/api/v1/me").status_code == 401


@pytest.mark.parametrize("path", ["/api/v1/me", "/api/v1/session"])
def test_missing_session_or_bearer_is_not_anonymous_admin(tmp_path, path):
    with TestClient(create_app(ApplicationService(ServiceConfiguration(str(tmp_path))))) as client:
        assert client.get(path).status_code == 401


def test_actual_json_body_limit_before_parsing(tmp_path):
    with TestClient(create_app(ApplicationService(ServiceConfiguration(str(tmp_path))))) as client:
        response = client.post("/api/v1/projects", content=b" " * (1024 * 1024 + 1), headers={"Content-Type":"application/json"})
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"
