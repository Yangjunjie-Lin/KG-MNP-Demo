"""Actual HTTP expiry, reauthentication and permission revocation, no disabled auth."""
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zhigou_toolchain.api.app import create_app
from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.models import ServiceConfiguration


def test_http_401_reauthentication_retains_project_and_never_replays_write(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    token, principal = service.tokens.create(principal_id="synthetic-session-test", principal_type="HUMAN",
        permissions={"*"}, project_ids=set(), created_by="test")
    with TestClient(create_app(service), base_url="https://testserver") as client:
        def login():
            result = client.post("/api/v1/session", headers={"Authorization": "Bearer " + token, "Origin": "https://testserver"})
            assert result.status_code == 200
            return {"Origin": "https://testserver", "X-CSRF-Token": result.json()["csrf_token"], "Idempotency-Key": "original-create"}
        headers = login()
        created = client.post("/api/v1/projects", headers=headers, json={"name": "synthetic-expiry", "domain_pack": "hr", "domain_pack_version": "0.1.0"})
        assert created.status_code == 200
        project_id = created.json()["project_id"]
        # Deterministic expiry injection in an isolated fixture, not a change
        # to the real 1800-second policy or a permanent browser credential.
        with sqlite3.connect(service.sessions.path) as connection:
            connection.execute("UPDATE sessions SET expires_at=0")
        assert client.get(f"/api/v1/projects/{project_id}/state").status_code == 401
        assert client.post("/api/v1/projects", headers=headers, json={"name": "must-not-replay", "domain_pack": "hr", "domain_pack_version": "0.1.0"}).status_code == 401
        login()
        restored = client.get(f"/api/v1/projects/{project_id}/state")
        assert restored.status_code == 200
        assert restored.json()["project"]["authority_revision"] == 0
        assert len(client.get("/api/v1/projects").json()["projects"]) == 1
        service.tokens.revoke(principal.token_id)
        assert client.get(f"/api/v1/projects/{project_id}/state").status_code == 401
        assert client.post("/api/v1/session", headers={"Authorization": "Bearer " + token, "Origin": "https://testserver"}).status_code == 401


def test_imported_approved_strings_do_not_become_action_authority(tmp_path):
    from zhigou_toolchain.contracts.document_io import atomic_write_json
    from zhigou_toolchain.services.errors import ServiceBoundaryError
    from zhigou_toolchain.services.models import OperationRequest
    from zhigou_toolchain.services.projects import get_project
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    _, principal = service.tokens.create(principal_id="synthetic-tamper-test", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="test")
    created = service.execute(OperationRequest("project.create", parameters={"name": "synthetic-import", "domain_pack": "hr", "domain_pack_version": "0.1.0"}), principal).payload
    project = get_project(service.root, created["project_id"])
    atomic_write_json(Path(project.root) / "registry" / "business-state.json", {"status": "APPROVED", "orders": {}})
    with pytest.raises(ServiceBoundaryError, match="server commit provenance"):
        service.execute(OperationRequest("business.inspect", project.project_id), principal)
