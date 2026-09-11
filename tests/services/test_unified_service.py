from __future__ import annotations

import asyncio

import httpx
import pytest

from kg_mnp.api.app import create_app
from kg_mnp.api.openapi import build_openapi
from kg_mnp.jobs.store import JobStore
from kg_mnp.jobs.worker import JobWorker
from kg_mnp.services.authorization import TokenStore
from kg_mnp.services.authorization_policy import reject_client_identity_claims
from kg_mnp.services.cli import main as service_cli_main
from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import (
    OperationRequest,
    PrincipalReference,
    ServiceConfiguration,
)


def _principal(*permissions: str, projects: set[str] | None = None) -> PrincipalReference:
    return PrincipalReference("alice", "HUMAN", frozenset(permissions), frozenset(projects or set()))


def test_local_token_store_persists_only_digest_and_revoke(tmp_path):
    store = TokenStore(tmp_path / "tokens.json")
    token, principal = store.create(principal_id="alice", principal_type="HUMAN", permissions={"project:read"}, project_ids=set(), created_by="local-admin")
    assert token not in (tmp_path / "tokens.json").read_text(encoding="utf-8")
    assert store.authenticate(token) == principal
    store.revoke(principal.token_id or "")
    with pytest.raises(ServiceBoundaryError) as error:
        store.authenticate(token)
    assert error.value.code == "AUTH_TOKEN_REVOKED"


def test_project_isolation_is_enforced_by_service(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    creator = _principal("project:write", "project:read")
    created = service.execute(OperationRequest("project.create", parameters={"name": "a", "domain_pack": "minimal", "domain_pack_version": "0.1.0"}), creator).payload
    owner = _principal("project:read", projects={created["project_id"]})
    outsider = _principal("project:read", projects={"urn:kg-mnp:project:" + "b" * 64})
    assert service.execute(OperationRequest("registry.verify", created["project_id"]), owner).payload["status"] == "VALID"
    with pytest.raises(ServiceBoundaryError) as error:
        service.execute(OperationRequest("registry.verify", created["project_id"]), outsider)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_client_cannot_inject_review_identity():
    with pytest.raises(ServiceBoundaryError) as error:
        reject_client_identity_claims({"reviewer_id": "attacker"})
    assert error.value.code == "AUTH_IDENTITY_CLAIM_REJECTED"


def test_durable_job_idempotency_and_fencing(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    principal = _principal("source:write", "project:read", projects={"urn:kg-mnp:project:" + "a" * 64})
    project = service.execute(OperationRequest("project.create", parameters={"name": "a", "domain_pack": "minimal", "domain_pack_version": "0.1.0"}), _principal("project:write", "project:read")).payload
    principal = _principal("source:write", "project:read", projects={project["project_id"]})
    request = OperationRequest("source.register", project["project_id"], {"path": "source.csv"}, "same-key")
    # A server path must never be accepted as an upload reference.
    with pytest.raises(ServiceBoundaryError) as blocked:
        service.execute(request, principal)
    assert blocked.value.code == "REQUEST_INVALID"
    first, _ = service.jobs.create(operation_id="source.register", project_id=project["project_id"], parameters={}, idempotency_key="same-key")
    replay, _ = service.jobs.create(operation_id="source.register", project_id=project["project_id"], parameters={}, idempotency_key="same-key")
    assert first.job_id == replay.job_id
    worker_result = JobWorker(service.jobs, service).run_once("worker-a")
    assert worker_result is not None
    assert service.jobs.get(first.job_id or "").status == "FAILED"

    store = JobStore(tmp_path / "independent.sqlite3")
    job, _ = store.create(operation_id="x", project_id=None, parameters={})
    claimed = store.claim(worker_id="one")
    assert claimed is not None
    with pytest.raises(ValueError):
        store.complete(job.job_id, worker_id="two", fencing_token=claimed.fencing_token, result={})
    assert store.complete(job.job_id, worker_id="one", fencing_token=claimed.fencing_token, result={}).status == "SUCCEEDED"


def test_openapi_and_real_asgi_http_auth_path(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    token, _principal_ref = service.tokens.create(principal_id="alice", principal_type="HUMAN", permissions={"project:read", "project:write"}, project_ids=set(), created_by="local-admin")
    app = create_app(service)
    document = build_openapi(service)
    operation_ids = [operation.get("operationId") for path in document["paths"].values() for operation in path.values() if isinstance(operation, dict) and "operationId" in operation]
    assert len(operation_ids) == len(set(operation_ids))

    async def request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            denied = await client.get("/api/v1/projects")
            allowed = await client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})
            return denied, allowed

    denied, allowed = asyncio.run(request())
    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_service_cli_help_is_explicit(capsys):
    assert service_cli_main(["--help"]) == 0
    assert "zhigou-toolchain service" in capsys.readouterr().out
