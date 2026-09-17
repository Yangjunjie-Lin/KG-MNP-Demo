import json
from dataclasses import replace
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from tests.services.test_modeling_workflow import call
from zhigou_toolchain.api.app import create_app
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.jobs.worker import JobWorker
from zhigou_toolchain.modeling.five_stage.agents import (
    AgentRun,
    PlanningAgent,
    RuleAgent,
    TaskExecutionAgent,
)
from zhigou_toolchain.modeling.five_stage.audit import ACTIVE_AUDIT, StepAudit
from zhigou_toolchain.services.errors import ServiceBoundaryError
from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.modeling_audit import (
    audit_index,
    audit_root,
    download_audit,
    read_events,
)
from zhigou_toolchain.services.models import OperationRequest, ServiceConfiguration


def unpack(raw):
    with ZipFile(BytesIO(raw)) as archive:
        return {n: archive.read(n) for n in archive.namelist()}


def test_each_agent_step_records_actual_before_and_after_without_mutating_input(tmp_path):
    assert PlanningAgent is RuleAgent  # Alias, not a new runtime identity.
    audit = StepAudit(tmp_path, {"job_id": "synthetic"}, content=True)
    run = AgentRun("session", "task", "1", [])
    token = ACTIVE_AUDIT.set(audit)
    source = {"value": "before", "api_key": "private-key", "acceptance": ["hidden-answer"]}
    try:
        for actor, stage, tool in [(PlanningAgent, 1, "input.profile"), (PlanningAgent, 2, "structure.design"),
                                  (TaskExecutionAgent, 3, "facts.normalize"), (PlanningAgent, 4, "integrity.check"),
                                  (TaskExecutionAgent, 5, "archive.verify")]:
            actor(run).execute(stage, tool, lambda: {"value": "after"}, inputs=source)
        with pytest.raises(ValueError):
            PlanningAgent(run).execute(4, "semantic.check", lambda: (_ for _ in ()).throw(ValueError("sensitive error")), inputs={})
    finally:
        ACTIVE_AUDIT.reset(token)
    assert source["api_key"] == "private-key"
    rows = [json.loads(p.read_bytes()) for p in sorted(tmp_path.glob("*.json"))]
    assert len(rows) == 12
    assert [r["phase"] for r in rows] == ["BEFORE", "AFTER"] * 6
    assert [r["metadata"]["stage_id"] for r in rows[::2]] == [1, 2, 3, 4, 5, 4]
    for before, after in zip(rows[::2], rows[1::2], strict=True):
        assert before["call_id"] == after["call_id"]
        assert after["previous_event_sha256"] == before["event_sha256"]
    assert rows[0]["payload"]["value"]["value"] == "before"
    assert rows[1]["payload"]["value"] == {"value": "after"}
    assert rows[-1]["metadata"]["status"] == "FAILED"
    assert "private-key" not in json.dumps(rows) and "hidden-answer" not in json.dumps(rows)
    assert "sensitive error" not in json.dumps(rows)


@pytest.fixture
def service_case(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path), modeling_audit_content_enabled=True,
        review_profile="DEVELOPMENT_SINGLE_REVIEWER"))
    token, principal = service.tokens.create(principal_id="synthetic-audit-owner", principal_type="HUMAN",
        permissions={"*"}, project_ids=set(), created_by="synthetic-test")
    project = service.execute(OperationRequest("project.create", parameters={"name": "audit", "domain_pack": "minimal",
        "domain_pack_version": "0.1.0"}), principal).payload["project_id"]
    seeded = call(service, principal, project, "modeling.tutorial.seed", {}, "seed")
    return service, principal, token, project, seeded


def test_worker_api_download_is_bound_private_and_keeps_failures(service_case):
    service, principal, token, project, seeded = service_case
    result = call(service, principal, project, "modeling.profile", {"run_id": seeded["run"]["run_id"]}, "profile")
    job = service.jobs.list_project(project)[0]
    events = read_events(service, job)
    assert events[0]["metadata"]["kind"] == "OPERATION"
    assert events[-1]["metadata"]["status"] == "COMMITTED"
    assert events[-1]["metadata"]["committed_result_sha256"] == semantic_hash(result)
    assert any(e["metadata"].get("native_agent_run_id") == result["agent_execution"]["run_id"] for e in events)
    raw = download_audit(service, principal, project, job.job_id)
    assert download_audit(service, principal, project, job.job_id) == raw
    files = unpack(raw)
    assert json.loads(files["manifest.json"])["pair_status"] == "CLOSED"
    with TestClient(create_app(service)) as client:
        path = f"/api/v1/projects/{project}/modeling/audits"
        headers = {"Authorization": "Bearer " + token}
        assert client.get(path, headers=headers).json()["agents"][0]["display_name"] == "规划 Agent"
        response = client.get(path + f"/{job.job_id}/archive", headers=headers)
        assert response.status_code == 200 and response.content == raw
        _, other = service.tokens.create(principal_id="other", principal_type="HUMAN", permissions={"project:read", "job:read", "trace:export", "source:export", "source:read", "package:read"}, project_ids=set(), created_by="test")
        with pytest.raises(ServiceBoundaryError):
            download_audit(service, other, project, job.job_id)
        # Same principal and project membership are insufficient without export grants.
        restricted_token, _ = service.tokens.create(principal_id=principal.principal_id,
            principal_type="HUMAN",
            permissions={"project:read", "job:read", "source:read"}, project_ids={project}, created_by="test")
        assert client.get(path + f"/{job.job_id}/archive", headers={"Authorization": "Bearer " + restricted_token}).status_code == 403
        assert client.get(path + f"/{job.job_id}/archive").status_code == 401
    service.execute(OperationRequest("modeling.profile", project, {"run_id": "urn:kg-mnp:ingestion-run:" + "0" * 64}, "fail"), principal)
    failed = JobWorker(service.jobs, service).run_once("failure-worker")
    assert failed.status == "FAILED"
    failed_events = read_events(service, failed)
    assert failed_events[-1]["metadata"]["status"] == "FAILED_NOT_COMMITTED"
    assert json.loads(unpack(download_audit(service, principal, project, failed.job_id))["manifest.json"])["commit_status"] == "NOT_COMMITTED"


def test_metadata_mode_and_recomputed_chain_cannot_change_bound_result(service_case):
    service, principal, _, project, seeded = service_case
    service.configuration = replace(service.configuration, modeling_audit_content_enabled=False)
    call(service, principal, project, "modeling.profile", {"run_id": seeded["run"]["run_id"]}, "metadata")
    job = service.jobs.list_project(project)[0]
    events = read_events(service, job)
    assert all(e["payload"]["capture"] == "METADATA_ONLY" and "value" not in e["payload"] for e in events)
    end = events[-1]
    end["metadata"]["committed_result_sha256"] = "0" * 64
    end["event_sha256"] = semantic_hash({k: v for k, v in end.items() if k != "event_sha256"})
    path = max(audit_root(service, project, job.job_id, job.attempt).glob("??????-*.json"))
    path.write_text(json.dumps(end), encoding="utf-8")
    with pytest.raises(ValueError, match="STEP_AUDIT_RESULT_MISMATCH"):
        download_audit(service, principal, project, job.job_id)


def test_human_scope_decision_is_not_an_agent_approval(service_case):
    service, principal, _, project, seeded = service_case
    scope = call(service, principal, project, "modeling.scope", {"run_id": seeded["run"]["run_id"],
        "description": "Synthetic", "object_families": ["Entity"], "in_scope": ["labels"],
        "namespace": "urn:synthetic:"}, "scope")["scope"]
    decision = call(service, principal, project, "modeling.scope.approve", {"scope_id": scope["scope_id"],
        "rationale": "Explicit synthetic review"}, "approve")
    assert "agent_execution" not in decision
    events = read_events(service, service.jobs.list_project(project)[0])
    assert len(events) == 2
    assert all(e["metadata"]["actor"] == "AUTHORIZED_REVIEWER" for e in events)
    assert events[-1]["payload"]["value"]["result"]["approval"] == decision["approval"]


def test_expired_partial_attempt_is_retained_after_real_worker_retry(service_case):
    service, principal, _, project, seeded = service_case
    params = {"run_id": seeded["run"]["run_id"]}
    service.execute(OperationRequest("modeling.profile", project, params, "retry"), principal)
    # Protocol fixture: a crashed worker leaves only its already-written BEFORE.
    abandoned = service.jobs.claim(worker_id="crash-fixture", lease_seconds=-1)
    binding = {k: getattr(abandoned, k) for k in ("project_id", "job_id", "attempt", "fencing_token", "request_digest", "operation_id")}
    audit = StepAudit(audit_root(service, project, abandoned.job_id, abandoned.attempt), binding)
    audit.before({"kind": "OPERATION", "stage_id": 1, "actor": "RuleAgent"}, params)
    service.jobs.requeue_local(abandoned.job_id, expected_attempt=1, requested_by=principal.principal_id)
    retried = JobWorker(service.jobs, service).run_once("real-retry")
    assert retried.status == "SUCCEEDED" and retried.attempt == 2
    first = unpack(download_audit(service, principal, project, retried.job_id, attempt=1))
    first_manifest = json.loads(first["manifest.json"])
    assert first_manifest["pair_status"] == "INTERRUPTED"
    assert first_manifest["commit_status"] == "NOT_COMMITTED"
    assert first_manifest["binding"]["fencing_token"] == abandoned.fencing_token
    second = unpack(download_audit(service, principal, project, retried.job_id, attempt=2))
    assert json.loads(second["manifest.json"])["pair_status"] == "CLOSED"
    index = [r for r in audit_index(service, principal, project)["records"] if r["job_id"] == retried.job_id]
    assert [r["attempt"] for r in index] == [2, 1]
    assert index[1]["job_status"] == "SUPERSEDED_ATTEMPT"
