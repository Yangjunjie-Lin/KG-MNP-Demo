"""Real Worker/CAS/API, with explicitly synthetic execution fixtures only.

No model calls, receiver contact or actual human evaluation is claimed here.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.services.test_modeling_workflow import call
from tests.upgrade.test_evolution_delivery import serial_trace
from zhigou_toolchain.api.app import create_app
from zhigou_toolchain.jobs.worker import JobWorker
from zhigou_toolchain.modeling.delivery.evolution import (
    evolution_files,
    parse_jsonl,
    validate_batch,
)
from zhigou_toolchain.modeling.delivery.exchange_io import read_archive
from zhigou_toolchain.services.errors import ServiceBoundaryError
from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.handoff import download
from zhigou_toolchain.services.models import OperationRequest, ServiceConfiguration
from zhigou_toolchain.services.ontology_traces import known_export_runs
from zhigou_toolchain.services.projects import get_project
from zhigou_toolchain.services.requests import validate_parameters


@pytest.fixture
def service_case(tmp_path):
    app = ApplicationService(ServiceConfiguration(str(tmp_path)))
    token, actor = app.tokens.create(principal_id="SYNTHETIC_CONTRACT_TEST", principal_type="HUMAN",
        permissions={"*"}, project_ids=set(), created_by="isolated-test")
    project = app.execute(OperationRequest("project.create", parameters={"name": "synthetic-protocol", "domain_pack": "hr", "domain_pack_version": "0.1.0"}), actor).payload["project_id"]
    return app, actor, token, project


def export_job(app, project, result):
    return next(j for j in app.jobs.list_project(project) if j.operation_id == "modeling.evolution.export" and (j.result or {}).get("sha256") == result["sha256"])


def test_empty_batch_real_api_worker_snapshot_and_permission(service_case):
    app, actor, token, project = service_case
    with TestClient(create_app(app)) as client:
        headers = {"Authorization": "Bearer " + token, "Idempotency-Key": "empty-api"}
        response = client.post("/api/v1/operations/modeling.evolution.export", headers=headers, json={"project_id": project, "batch_id": "empty-api"})
        assert response.status_code == 202, response.text
        job = JobWorker(app.jobs, app).run_once("empty-test")
        assert job.status == "SUCCEEDED", job.error
        raw = download(app, actor, project, job.job_id)
        files = read_archive(raw)
        assert json.loads(files["upstream_manifest.json"])["files"] == []
        assert not any(n.startswith(("executions/", "reviews/")) for n in files)
        assert client.get(f"/api/v1/projects/{project}/handoffs/{job.job_id}/archive", headers=headers).content == raw
        repeated = call(app, actor, project, "modeling.evolution.export", {"batch_id": "empty-api"}, "same-bytes-new-request")
        assert repeated["sha256"] == job.result["sha256"]
        _, denied = app.tokens.create(principal_id="no-trace", principal_type="HUMAN", permissions={"project:read", "source:read", "package:export"}, project_ids={project}, created_by="test")
        with pytest.raises(ServiceBoundaryError):
            download(app, denied, project, job.job_id)


@pytest.mark.parametrize("payload,valid", [
    ({"job_id": "selected", "verdict": "pass"}, True),
    ({"job_id": "selected", "verdict": "fail", "annotations": []}, True),
    ({"job_id": "selected", "verdict": "fail"}, False),
    ({"job_id": "selected", "verdict": "accepted"}, False),
    ({"exec_id": "untrusted", "verdict": "pass"}, False),
    ({"job_id": "selected", "verdict": "pass", "reviewer": "spoofed"}, False),
])
def test_review_dto_conditional_fields(payload, valid):
    request = OperationRequest("modeling.evolution.review", "test", payload)
    if valid:
        validate_parameters(request)
    else:
        with pytest.raises(ServiceBoundaryError, match="request"):
            validate_parameters(request)


def test_history_review_roundtrip_real_worker_with_synthetic_boundary(service_case, monkeypatch):
    app, actor, token, project = service_case
    trace = serial_trace()
    run_id = trace["bindings"]["transport_run_id"]
    # Only the trace boundary is a labeled fixture. Immutable commit, auth,
    # review, subsequent review-only export and download use actual services.
    with monkeypatch.context() as boundary:
        boundary.setattr("zhigou_toolchain.services.ontology_traces.export_trace", lambda *a: (
            evolution_files([trace], batch_id="synthetic-execution", allow_synthetic=True),
            {"status": "EXPORTED", "format": "evolution-upstream/v2", "nature": "SYNTHETIC_CONTRACT_FIXTURE", "receiver_status": "NOT_CONTACTED"}))
        receipt = call(app, actor, project, "modeling.evolution.export", {"batch_id": "synthetic-execution"}, "synthetic-execution")
    history_job = export_job(app, project, receipt)
    known = known_export_runs(app, get_project(app.root, project), actor, [history_job.job_id])
    assert set(known) == {run_id} and known[run_id]["receiver_status"] == "NOT_CONTACTED"
    optional = {"violations": [{"code": "synthetic-ontology-code", "evidence": {"iri": "urn:synthetic"}, "suggestion": "check", "severity": "minor"}],
                "corrected_answer": ["preserve", {"opaque": None, "role": "business-value-not-identity", "approved": False}]}
    with TestClient(create_app(app)) as client:
        response = client.post("/api/v1/operations/modeling.evolution.review", headers={"Authorization": "Bearer " + token, "Idempotency-Key": "pass-review"},
            json={"project_id": project, "exec_id": run_id, "execution_export_job_id": history_job.job_id, "verdict": "pass", **optional})
        assert response.status_code == 202, response.text
        review_job = JobWorker(app.jobs, app).run_once("synthetic-review")
        assert review_job.status == "SUCCEEDED", review_job.error
    review_id = review_job.result["review_id"]
    stored = json.loads((Path(get_project(app.root, project).root) / "artifacts/builds/trajectory-reviews" / (review_id + ".json")).read_bytes())["review"]
    assert stored["reviewer"] == actor.principal_id and stored["verdict"] == "pass" and "annotations" not in stored
    assert {k: stored[k] for k in optional} == optional
    params = {"batch_id": "only-reviews", "review_ids": [review_id]}
    exported = call(app, actor, project, "modeling.evolution.export", params, "only-reviews")
    job = export_job(app, project, exported)
    files = read_archive(download(app, actor, project, job.job_id))
    assert not any(n.startswith("executions/") for n in files)
    assert parse_jsonl(files["reviews/reviews-only-reviews.jsonl"]) == [stored]
    assert validate_batch(files, known_run_ids=known)["status"] == "LOCAL_PROTOCOL_VALID"
    import os
    import subprocess
    import sys

    from zhigou_toolchain.modeling.delivery.exchange_io import write_directory
    directory = app.root / "synthetic-review-batch"
    write_directory(directory, files, manifest="upstream_manifest.json")
    env = {**os.environ, "ZHIGOU_TOKEN": token, "PYTHONUTF8": "1"}
    env.pop("KG_MNP_TOKEN", None)
    arguments = ["--workspace", str(app.root), "--project-id", project, "--known-run-export-job-id", history_job.job_id]
    for command in (["validate-evolution", str(directory), *arguments],
                    ["assemble-handoff", str(app.root / "synthetic-review-cover"), "--evolution", str(directory), *arguments]):
        proc = subprocess.run([sys.executable, "-m", "zhigou_toolchain.modeling.delivery.cli", *command], env=env, capture_output=True, check=False)
        assert proc.returncode == 0, proc.stderr.decode("utf-8")
    assert call(app, actor, project, "modeling.evolution.export", params, "repeat-same-snapshot")["sha256"] == exported["sha256"]
    with pytest.raises(ServiceBoundaryError):
        call(app, actor, project, "modeling.evolution.export", {**params, "batch_id": "duplicate-review"}, "duplicate-review")
    other = app.execute(OperationRequest("project.create", parameters={"name": "wrong-project", "domain_pack": "hr", "domain_pack_version": "0.1.0"}), actor).payload["project_id"]
    with pytest.raises(ValueError, match="SCOPE"):
        known_export_runs(app, get_project(app.root, other), actor, [history_job.job_id])
    with pytest.raises(ServiceBoundaryError):
        call(app, actor, project, "modeling.evolution.review", {"exec_id": "invented", "execution_export_job_id": history_job.job_id, "verdict": "pass"}, "unknown-run")
    app.tokens.revoke(actor.token_id)
    with pytest.raises(ServiceBoundaryError):
        known_export_runs(app, get_project(app.root, project), actor, [history_job.job_id])


def test_service_actor_cannot_submit_human_review(service_case):
    app, _, _, project = service_case
    _, actor = app.tokens.create(principal_id="synthetic-agent", principal_type="SERVICE", permissions={"*"}, project_ids={project}, created_by="test")
    with pytest.raises(ServiceBoundaryError, match="human"):
        call(app, actor, project, "modeling.evolution.review", {"job_id": "not-an-authority", "verdict": "pass"}, "agent-denied")
