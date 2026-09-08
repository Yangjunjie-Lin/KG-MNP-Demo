"""Fault injection at the actual core authority switch, not only Job completion."""
from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path

import pytest

from kg_mnp.jobs.worker import JobWorker
from kg_mnp.services import execution, sources
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest, ServiceConfiguration
from kg_mnp.services.projects import get_project, load_catalog
from kg_mnp.services.uploads import receive_upload


@pytest.fixture
def pending(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    _, principal = service.tokens.create(principal_id="synthetic-reviewer", principal_type="HUMAN",
                                         permissions={"*"}, project_ids=set(), created_by="test")
    project = service.execute(OperationRequest("project.create", parameters={"name": "fencing", "domain_pack": "minimal",
                                                                            "domain_pack_version": "0.1.0"}), principal).payload

    async def chunks():
        yield b'{"code":"synthetic-1"}'

    result = asyncio.run(receive_upload(service, project["project_id"], principal, chunks(), filename="data.json",
                                        media_type="application/json", idempotency_key="fenced"))
    return service, principal, project["project_id"], result.job_id


@pytest.mark.parametrize("fault", ["lease", "revoked", "cancel", "superseded", "write_failure", "identity", "input_changed"])
def test_computed_artifacts_cannot_publish_after_losing_authority(pending, monkeypatch, fault):
    service, principal, project_id, job_id = pending
    before = get_project(service.root, project_id)
    digest = execution.tree_digest(Path(before.root))
    original = sources.execute

    def compute(*args):
        result = original(*args)
        if fault == "revoked":
            service.tokens.revoke(principal.token_id)
        elif fault == "identity":
            records = service.tokens._read()
            records["tokens"][principal.token_id]["principal_id"] = "changed-during-computation"
            service.tokens._write(records)
        elif fault == "cancel":
            service.jobs.cancel(job_id)
        elif fault == "write_failure":
            raise OSError("simulated mid-computation failure")
        elif fault == "input_changed":
            # Original authority changes after private computation: no stale
            # result may publish over this newer input, or silently repair it.
            path = Path(before.root) / "project.yaml"
            path.write_bytes(path.read_bytes() + b"\n# changed during computation\n")
        else:
            with sqlite3.connect(service.jobs.path) as conn:
                if fault == "lease":
                    conn.execute("UPDATE jobs SET lease_expires_at=? WHERE job_id=?", (time.time() - 1, job_id))
                else:
                    conn.execute("UPDATE jobs SET fencing_token=fencing_token+1,lease_owner='replacement' WHERE job_id=?", (job_id,))
        return result

    monkeypatch.setattr(sources, "execute", compute)
    result = JobWorker(service.jobs, service).run_once("old-worker")
    assert result.status != "SUCCEEDED"
    assert get_project(service.root, project_id) == before
    if fault == "input_changed":
        assert execution.tree_digest(Path(before.root)) != digest
        assert (Path(before.root) / "project.yaml").read_bytes().endswith(b"# changed during computation\n")
    else:
        assert execution.tree_digest(Path(before.root)) == digest
    assert job_id not in load_catalog(service.root).get("commits", {})
    assert not list((Path(before.root) / "sources").rglob("*.json"))


@pytest.mark.parametrize("when", ["before", "after"])
def test_atomic_publication_and_restart_receipt_recovery(pending, monkeypatch, when):
    service, _, project_id, job_id = pending
    before = get_project(service.root, project_id)
    original = execution.save_catalog

    class ProcessDied(BaseException):
        pass

    def crash(root, catalog):
        if when == "after":
            original(root, catalog)
        raise ProcessDied()

    monkeypatch.setattr(execution, "save_catalog", crash)
    job = service.jobs.claim(worker_id="crashing-worker")
    with pytest.raises(ProcessDied):
        service.execute_job(job, service.jobs.parameters(job_id))
    restarted = ApplicationService(service.configuration)
    if when == "before":
        assert get_project(service.root, project_id) == before
        assert restarted.recover_job(job) is None
        assert not list((Path(before.root) / "sources").rglob("*.json"))
    else:
        recovered = restarted.recover_job(job)
        assert recovered.status == "SUCCEEDED"
        assert recovered.result["source"]["source_id"]
        assert get_project(service.root, project_id).authority_revision == 1
        assert restarted.recover_job(job).result == recovered.result
        assert restarted.jobs.cancel(job_id).status == "SUCCEEDED"


def test_commit_receipt_loss_is_not_job_failure(pending, monkeypatch):
    service, _, project_id, job_id = pending
    def lost(*args, **kwargs):
        raise OSError("completion response lost")
    monkeypatch.setattr(service.jobs, "complete", lost)
    result = JobWorker(service.jobs, service).run_once("worker")
    assert result.status == "SUCCEEDED"
    assert result.job_id == job_id
    assert get_project(service.root, project_id).authority_revision == 1


def test_two_workers_cannot_claim_same_job(pending):
    service, _, _, job_id = pending
    first = service.jobs.claim(worker_id="first")
    assert first.job_id == job_id
    assert service.jobs.claim(worker_id="second") is None
    result = service.execute_job(first, service.jobs.parameters(job_id))
    assert result["batch"]["sources"]
    assert service.recover_job(first).status == "SUCCEEDED"
