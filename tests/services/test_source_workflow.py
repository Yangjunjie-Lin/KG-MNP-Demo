"""Real network source/ingestion acceptance; never substitutes business handlers."""
from __future__ import annotations

import json
import socket
from threading import Thread
from time import monotonic

import httpx
import pytest
import uvicorn

from kg_mnp.api.app import create_app
from kg_mnp.jobs.worker import JobWorker
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import ServiceConfiguration


@pytest.fixture
def server(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path), max_upload_bytes=256))
    token, principal = service.tokens.create(principal_id="source-tester", principal_type="HUMAN",
                                            permissions={"*"}, project_ids=set(), created_by="synthetic-test")
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    server = uvicorn.Server(uvicorn.Config(create_app(service), log_level="error", access_log=False))
    thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{sock.getsockname()[1]}",
                          headers={"Authorization": f"Bearer {token}"}, timeout=60) as client:
            deadline = monotonic() + 15
            while not server.started:
                if monotonic() > deadline:
                    pytest.fail("owned API did not start")
                thread.join(.02)
            response = client.post("/api/v1/projects", json={"name": "真实资料链路", "domain_pack": "minimal",
                                                           "domain_pack_version": "0.1.0"})
            assert response.status_code == 200, response.text
            yield service, principal, client, response.json()["project_id"]
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
        assert not thread.is_alive()


def upload(client, project_id, content=b'{"code":"SYNTH-01","label":"synthetic"}', key="upload-1"):
    return client.post(f"/api/v1/projects/{project_id}/sources", content=content,
                       headers={"Content-Type": "application/json", "X-Filename": "synthetic.json",
                                "Idempotency-Key": key})


def finish(service, client, job_id):
    observed = []
    execute = service.execute_job
    def capture(job, parameters):
        try:
            return execute(job, parameters)
        except Exception as exc:
            observed.append(exc)
            raise
    service.execute_job = capture
    try:
        result = JobWorker(service.jobs, service).run_once("source-test-worker")
    finally:
        service.execute_job = execute
    if observed:
        raise observed[0]
    assert result and result.job_id == job_id
    assert result.status == "SUCCEEDED", result.error
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["result"]
    return response.json()["result"]


def test_real_tcp_source_ingestion_evidence_chain(server):
    service, _, client, project_id = server
    uploaded = upload(client, project_id)
    assert uploaded.status_code == 202, uploaded.text
    registered = finish(service, client, uploaded.json()["job_id"])
    source_id, batch_id = registered["source"]["source_id"], registered["batch"]["batch_id"]
    source_response = client.get(f"/api/v1/projects/{project_id}/sources/{source_id}")
    assert source_response.status_code == 200
    assert source_response.json()["source"]["source_id"] == source_id
    assert client.get(f"/api/v1/projects/{project_id}/sources").json()["sources"][0]["source_id"] == source_id
    replay = upload(client, project_id)
    assert replay.status_code == 202
    assert replay.json()["job_id"] == uploaded.json()["job_id"]
    planned = client.post(f"/api/v1/projects/{project_id}/ingestion/plans", json={"batch_id": batch_id},
                          headers={"Idempotency-Key": "plan-1"})
    assert planned.status_code == 202, planned.text
    plan = finish(service, client, planned.json()["job_id"])["plan"]
    assert plan["status"] == "READY"
    launched = client.post(f"/api/v1/projects/{project_id}/ingestion/runs", json={"plan_id": plan["plan_id"]},
                           headers={"Idempotency-Key": "run-1"})
    assert launched.status_code == 202, launched.text
    run = finish(service, client, launched.json()["job_id"])["run"]
    inspected = client.get(f"/api/v1/projects/{project_id}/ingestion/runs/{run['run_id']}")
    assert inspected.status_code == 200, inspected.text
    dataset = inspected.json()["dataset"]
    assert dataset["items"] and dataset["evidence_records"]
    trace = client.post("/api/v1/operations/ingestion.trace", json={"project_id":project_id,"run_id":run["run_id"],"item_id":dataset["items"][0]["item_id"]})
    assert trace.status_code == 200
    assert trace.json()["payload"]["evidence"]
    traced = client.get(f"/api/v1/projects/{project_id}/evidence", params={"run_id": run["run_id"]})
    assert traced.status_code == 200, traced.text
    assert any(record["source_id"] == source_id for record in traced.json()["evidence"])
    downloaded = client.get(f"/api/v1/projects/{project_id}/sources/{source_id}/content")
    assert downloaded.status_code == 200
    assert json.loads(downloaded.content)["code"] == "SYNTH-01"
    assert "attachment" in downloaded.headers["content-disposition"]
    assert str(service.root) not in inspected.text


def test_streaming_limit_is_actual_bytes_and_cleans_pending_upload(server):
    service, _, client, project_id = server
    response = client.post(f"/api/v1/projects/{project_id}/sources", content=iter([b"a" * 200, b"b" * 200]),
                           headers={"Content-Type": "application/json", "X-Filename": "huge.json",
                                    "Idempotency-Key": "large"})
    assert response.status_code == 413, response.text
    assert not list(service.root.glob("projects/*/tmp/uploads/*.part"))
    assert JobWorker(service.jobs, service).run_once() is None


def test_source_permission_and_server_paths_are_rejected(server):
    service, _, client, project_id = server
    token, _ = service.tokens.create(principal_id="outsider", principal_type="HUMAN",
                                     permissions={"source:read", "source:write"}, project_ids=set(), created_by="test")
    response = client.get(f"/api/v1/projects/{project_id}/sources", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403, response.text
    response = client.post("/api/v1/operations/source.register", json={"project_id": project_id, "path": "C:/private"},
                           headers={"Idempotency-Key": "bad-path"})
    assert response.status_code == 422, response.text


def test_display_filename_cannot_be_an_authoritative_path(server):
    service, _, client, project_id = server
    response = client.post(f"/api/v1/projects/{project_id}/sources", content=b"{}",
        headers={"X-Filename":"../private.json", "Content-Type":"application/json", "Idempotency-Key":"traversal"})
    assert response.status_code == 422
    assert JobWorker(service.jobs, service).run_once() is None
