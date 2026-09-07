"""Prompt 8 regressions: real workspace/identity boundaries, never mock success."""
from __future__ import annotations

import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from kg_mnp.api.app import create_app
from kg_mnp.jobs.store import JobStore
from kg_mnp.jobs.worker import JobWorker
from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import (
    OperationRequest,
    PrincipalReference,
    ServiceConfiguration,
)
from kg_mnp.services.operations import HANDLERS
from kg_mnp.services.projects import get_project
from kg_mnp.workspace.validation import validate_workspace


@pytest.fixture
def service(tmp_path):
    return ApplicationService(ServiceConfiguration(str(tmp_path)))


def identity(service, name="alice", permissions=None, principal_type="HUMAN"):
    return service.tokens.create(
        principal_id=name, principal_type=principal_type,
        permissions=permissions or {"project:read", "project:write", "source:write"},
        project_ids=set(), created_by="explicit-test-bootstrap",
    )


def create(service, principal, name="example", key="create-1", version="0.1.0"):
    return service.execute(OperationRequest("project.create", parameters={
        "name": name, "domain_pack": "minimal", "domain_pack_version": version,
    }, idempotency_key=key), principal).payload


def test_created_project_is_valid_workspace_without_path_disclosure(service):
    _, alice = identity(service)
    result = create(service, alice)
    handle = get_project(service.jobs.path.parents[1], result["project_id"])
    assert validate_workspace(handle.root).status == "VALID"
    assert "root" not in result
    assert result["manifest_project_id"]
    assert result["status"] == "VALID"


def test_pack_version_unavailable_does_not_create_project(service):
    _, alice = identity(service)
    with pytest.raises(ServiceBoundaryError) as error:
        create(service, alice, version="99.0.0")
    assert error.value.code == "DOMAIN_PACK_VERSION_UNAVAILABLE"
    assert service.execute(OperationRequest("project.list"), alice).payload["projects"] == []


def test_discovery_is_real_and_available_before_project_creation(service):
    _, alice = identity(service)
    packs = service.execute(OperationRequest("domain-pack.discover"), alice).payload["domain_packs"]
    minimal = next(pack for pack in packs if pack["pack_id"] == "minimal")
    assert minimal["pack_version"] == "0.1.0"
    assert minimal["lock_status"] == "VERIFIED"
    assert minimal["availability"] == "AVAILABLE"


def test_project_list_and_open_reject_empty_scope_outsider(service):
    _, alice = identity(service)
    _, bob = identity(service, "bob")
    project = create(service, alice)
    assert service.execute(OperationRequest("project.list"), bob).payload["projects"] == []
    with pytest.raises(ServiceBoundaryError) as error:
        service.execute(OperationRequest("project.open", parameters={"project_id": project["project_id"]}), bob)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_sync_idempotency_rejects_changed_body(service):
    _, alice = identity(service)
    first = create(service, alice)
    assert create(service, alice) == first
    with pytest.raises(ServiceBoundaryError) as error:
        create(service, alice, name="changed")
    assert error.value.code == "IDEMPOTENCY_CONFLICT"


def test_health_is_minimal_even_for_authenticated_reader(service):
    token, _ = identity(service)
    with TestClient(create_app(service)) as client:
        assert client.get("/healthz").json() == {"status": "ALIVE"}
        response = client.get("/api/v1/health", headers={"Authorization": f"Bearer {token}"})
        assert response.json() == {"status": "ALIVE"}


@pytest.mark.parametrize("claim", ["__principal", "reviewer_id", "approved", "explicit_human_action"])
def test_client_identity_claims_rejected_recursively(service, claim):
    _, alice = identity(service)
    with pytest.raises(ServiceBoundaryError) as error:
        service.execute(OperationRequest("project.list", parameters={"nested": {claim: "forged"}}), alice)
    assert error.value.code == "AUTH_IDENTITY_CLAIM_REJECTED"


def test_jobs_cannot_be_read_by_another_principal(service):
    _, alice = identity(service)
    _, bob = identity(service, "bob")
    project = create(service, alice)
    job, _ = service.jobs.create(operation_id="source.register", project_id=project["project_id"],
                                 parameters={"__principal": alice.to_dict()})
    for operation in ("job.get", "job.events"):
        with pytest.raises(ServiceBoundaryError) as error:
            service.execute(OperationRequest(operation, parameters={"job_id": job.job_id}), bob)
        assert error.value.status_code == 403


def test_revoked_job_principal_cannot_execute(service):
    _, alice = identity(service)
    project = create(service, alice)
    # A persisted P7 job is deliberately reconstructed here. The worker must not
    # trust its serialized grants even when migrating an older queue.
    job, _ = service.jobs.create(operation_id="project.lock", project_id=project["project_id"],
                                 parameters={"__principal": alice.to_dict()})
    service.tokens.revoke(alice.token_id)
    result = JobWorker(service.jobs, service).run_once("revocation-test")
    assert result.job_id == job.job_id
    assert result.status == "FAILED"
    assert result.error["code"] == "AUTH_TOKEN_REVOKED"


def test_incomplete_p7_project_is_not_silently_upgraded(service):
    root = service.jobs.path.parents[1]
    old = root / "projects" / "old"
    old.mkdir(parents=True)
    old_lock = b'{"status":"LOCKED"}'
    (old / "project.lock.json").write_bytes(old_lock)
    (root / "service-projects.json").write_text(json.dumps({"projects": {"old": {
        "project_id": "old", "project_name": "legacy", "root": str(old), "status": "OPEN",
    }}}), encoding="utf-8")
    admin = PrincipalReference("admin", permissions=frozenset({"project:read", "project:admin"}))
    row = service.execute(OperationRequest("project.open", parameters={"project_id": "old"}), admin).payload
    assert row["status"] == "LEGACY_INCOMPLETE"
    assert row["migration_status"] == "NEW_WORKSPACE_REQUIRED"
    assert (old / "project.lock.json").read_bytes() == old_lock


def test_empty_pack_root_and_parse_failure_are_distinct(tmp_path):
    empty = tmp_path / "packs"
    empty.mkdir()
    service = ApplicationService(ServiceConfiguration(str(tmp_path / "service"), domain_packs_root=str(empty)))
    _, alice = identity(service)
    assert service.execute(OperationRequest("domain-pack.discover"), alice).payload == {"domain_packs": []}
    broken = empty / "broken"
    broken.mkdir()
    (broken / "pack.yaml").write_text("pack_id: [broken", encoding="utf-8")
    with pytest.raises(ServiceBoundaryError) as error:
        service.execute(OperationRequest("domain-pack.discover"), alice)
    assert error.value.code == "DOMAIN_PACK_DISCOVERY_FAILED"
    with pytest.raises(ServiceBoundaryError) as denied:
        service.execute(OperationRequest("domain-pack.discover"), PrincipalReference("no-permission"))
    assert denied.value.status_code == 403


def test_formal_lock_check_is_byte_preserving_and_rejects_tampering(service):
    _, alice = identity(service)
    project = create(service, alice)
    path = get_project(service.root, project["project_id"]).registry_root.parents[1] / "project.lock.json"
    before = path.read_bytes()
    request = OperationRequest("project.lock", project["project_id"], idempotency_key="lock-1")
    assert service.execute(request, alice).payload["status"] == "VALID"
    assert path.read_bytes() == before
    path.write_bytes(b'{"status":"LOCKED"}')
    with pytest.raises(ServiceBoundaryError) as error:
        service.execute(OperationRequest("project.lock", project["project_id"], idempotency_key="lock-2"), alice)
    assert error.value.code == "PROJECT_REBIND_FORBIDDEN"
    assert path.read_bytes() == b'{"status":"LOCKED"}'


def test_job_idempotency_scope_includes_principal_project_operation(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    common = {"project_id": "p1", "parameters": {"value": 1}, "idempotency_key": "key"}
    first, _ = store.create(operation_id="a", principal_id="alice", **common)
    replay, found = store.create(operation_id="a", principal_id="alice", **common)
    bob, _ = store.create(operation_id="a", principal_id="bob", **common)
    other, _ = store.create(operation_id="b", principal_id="alice", **common)
    assert found and first.job_id == replay.job_id
    assert len({first.job_id, bob.job_id, other.job_id}) == 3
    with pytest.raises(ValueError, match="different request"):
        store.create(operation_id="a", principal_id="alice", project_id="p1", parameters={"value": 2}, idempotency_key="key")
    assert JobStore(store.path).get(first.job_id).status == "QUEUED"


def test_sync_idempotency_is_concurrent_and_principal_scoped(service):
    _, alice = identity(service)
    _, bob = identity(service, "bob")
    from kg_mnp.services.idempotency import IdempotencyStore
    calls = []
    request = OperationRequest("project.lock", "p", {"value": 1}, "key")

    def invoke(principal):
        try:
            return service.idempotency.execute(request, principal, lambda: calls.append(principal.principal_id) or {"value": 1})
        except ServiceBoundaryError as exc:
            assert exc.code == "RECOVERY_REQUIRED"
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(invoke, [alice] * 4))
    assert calls == ["alice"]
    assert invoke(bob) == {"value": 1}
    assert calls == ["alice", "bob"]
    restarted = IdempotencyStore(service.idempotency.path)
    assert restarted.execute(request, alice, lambda: pytest.fail("must replay")) == {"value": 1}


def test_expired_lease_cannot_complete_or_renew_and_is_recovery_required(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    pending, _ = store.create(operation_id="external", project_id=None, parameters={})
    job = store.claim(worker_id="old")
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE jobs SET lease_expires_at=? WHERE job_id=?", (time.time() - 10, job.job_id))
    with pytest.raises(ValueError):
        store.require_lease(job)
    with pytest.raises(ValueError):
        store.renew(job.job_id, worker_id="old", fencing_token=job.fencing_token)
    with pytest.raises(ValueError):
        store.complete(job.job_id, worker_id="old", fencing_token=job.fencing_token, result={})
    assert store.claim(worker_id="new") is None
    assert store.get(pending.job_id).status == "RECOVERY_REQUIRED"


def test_token_expiration_and_current_permission_revalidation(service):
    token, principal = service.tokens.create(principal_id="expired", principal_type="HUMAN", permissions={"*"},
                                           project_ids=set(), created_by="test", expires_at=time.time() - 1)
    for action in (lambda: service.authenticate(f"Bearer {token}"), lambda: service.execute(OperationRequest("project.list"), principal)):
        with pytest.raises(ServiceBoundaryError) as error:
            action()
        assert error.value.code == "AUTH_TOKEN_EXPIRED"


def test_service_account_cannot_approve_scope_or_reviews(service):
    _, robot = identity(service, "robot", permissions={"*"}, principal_type="SERVICE")
    for operation in ("modeling.scope.approve", "review.action", "release.review"):
        with pytest.raises(ServiceBoundaryError) as error:
            service.execute(OperationRequest(operation, "project", {}, "review"), robot)
        assert error.value.code == "HUMAN_APPROVAL_REQUIRED"


def test_legacy_job_payloads_are_not_returned_and_cancel_is_scoped(service):
    _, alice = identity(service, permissions={"project:read", "project:write", "job:cancel"})
    _, bob = identity(service, "bob", permissions={"project:read", "job:cancel"})
    project = create(service, alice)
    job, _ = service.jobs.create(operation_id="old", project_id=project["project_id"],
                                 parameters={"__principal": alice.to_dict(), "path": str(service.root)})
    for operation in ("job.get", "job.events"):
        response = service.execute(OperationRequest(operation, parameters={"job_id": job.job_id}), alice).payload
        assert str(service.root) not in json.dumps(response)
        assert "token_id" not in json.dumps(response)
    with pytest.raises(ServiceBoundaryError):
        service.cancel_job(job.job_id, bob)
    assert service.cancel_job(job.job_id, alice)["status"] == "CANCELLED"
    assert JobWorker(service.jobs, service).run_once() is None


def test_resource_api_and_compatibility_dto_reject_unknown_fields(service):
    token, _ = identity(service)
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(create_app(service)) as client:
        assert client.get("/api/v1/me", headers=headers).json()["principal_id"] == "alice"
        caps = client.get("/api/v1/capabilities", headers=headers).json()["capabilities"]
        assert next(item for item in caps if item["operation_id"] == "source.register")["status"] == "NOT_IMPLEMENTED"
        assert client.get("/api/v1/doctor", headers=headers).status_code == 403
        assert client.get("/api/v1/projects", headers={**headers, "Origin": "https://attacker.invalid"}).status_code == 403
        invalid = client.post("/api/v1/projects", headers=headers, json={"name": "x", "path": "private"})
        assert invalid.status_code == 422
        assert "private" not in invalid.text
        invalid = client.post("/api/v1/operations/project.list", headers=headers, json={"path": "private"})
        assert invalid.status_code == 422
        assert "private" not in invalid.text
        assert client.get("/health/live").headers["x-content-type-options"] == "nosniff"


def test_owner_open_validate_catalog_pack_inspect_and_empty_environment(service):
    from kg_mnp.lifecycle.environment import init_environment

    _, alice = identity(service)
    project = create(service, alice)
    for operation in ("project.open", "project.validate"):
        assert service.execute(OperationRequest(operation, project["project_id"]), alice).payload["status"] == "VALID"
    result = service.execute(OperationRequest("domain-pack.inspect", parameters={"pack_id": "minimal", "pack_version": "0.1.0"}), alice).payload
    assert result["availability"] == "AVAILABLE" and result["content_digest"]
    with pytest.raises(ServiceBoundaryError) as missing:
        service.execute(OperationRequest("domain-pack.inspect", parameters={"pack_id": "minimal", "pack_version": "9.9.9"}), alice)
    assert missing.value.status_code == 404
    catalog = service.execute(OperationRequest("operation.catalog"), alice).payload
    assert len(catalog["operations"]) == 53
    assert len([item for item in catalog["coverage"] if item["service_handler"]]) == 14
    environment = init_environment(get_project(service.root, project["project_id"]).registry_root, environment_name="test")
    pointer = service.execute(OperationRequest("environment.inspect", project["project_id"], {"environment_id": environment["environment_id"]}), alice).payload
    assert pointer["selection_status"] == "NO_RELEASE_SELECTED"
    assert pointer["active_release_id"] is None
    assert pointer["generation"] == 0


@pytest.mark.parametrize("operation,params", [
    ("package.inspect", {"package_id": "unknown"}),
    ("release.inspect", {"release_id": "unknown"}),
    ("environment.inspect", {"environment_id": "../../secret"}),
])
def test_missing_artifact_does_not_become_success_or_path_lookup(service, operation, params):
    _, alice = identity(service, permissions={"project:read", "project:write", "package:read"})
    project = create(service, alice)
    with pytest.raises(ServiceBoundaryError) as missing:
        service.execute(OperationRequest(operation, project["project_id"], params), alice)
    assert missing.value.code == "ARTIFACT_NOT_FOUND"


def test_failed_sync_request_and_unknown_outcome_are_not_reexecuted(service):
    _, alice = identity(service)
    calls = []

    def failed():
        calls.append("failure")
        raise ServiceBoundaryError("DELIBERATE_FAILURE", "negative test", status_code=422)

    request = OperationRequest("project.create", None, {}, "failed")
    for _ in range(2):
        with pytest.raises(ServiceBoundaryError, match="negative test"):
            service.idempotency.execute(request, alice, failed)
    assert calls == ["failure"]

    def interrupted():
        raise RuntimeError("simulated process interruption at boundary")

    request = OperationRequest("project.create", None, {}, "interrupted")
    with pytest.raises(RuntimeError):
        service.idempotency.execute(request, alice, interrupted)
    with pytest.raises(ServiceBoundaryError) as pending:
        service.idempotency.execute(request, alice, lambda: pytest.fail("must not reexecute"))
    assert pending.value.code == "RECOVERY_REQUIRED"


@pytest.mark.parametrize("operation", sorted(HANDLERS))
def test_missing_permission_is_denied_before_handler(service, operation):
    with pytest.raises(ServiceBoundaryError) as denied:
        service.execute(OperationRequest(operation, "untrusted-project", {}), PrincipalReference("no-grants"))
    assert denied.value.code == "FORBIDDEN"
