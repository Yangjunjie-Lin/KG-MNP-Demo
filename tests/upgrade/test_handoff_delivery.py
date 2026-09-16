"""Real core/service handoff, explicitly synthetic identities and data."""
from __future__ import annotations

import json
import os
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from tests.upgrade.test_full_chain import forestry_case, hr_case  # noqa: F401
from zhigou_toolchain.api.app import create_app
from zhigou_toolchain.ingestion.source_store import SourceStore
from zhigou_toolchain.modeling.delivery.exchange_io import digest
from zhigou_toolchain.modeling.delivery.handoff import verify_handoff
from zhigou_toolchain.modeling.delivery.v3 import read_zip
from zhigou_toolchain.services.errors import ServiceBoundaryError
from zhigou_toolchain.services.handoff import download
from zhigou_toolchain.services.modeling_sessions import read
from zhigou_toolchain.services.models import OperationRequest
from zhigou_toolchain.services.projects import get_project


def request_for(case):
    project = get_project(case["service"].root, case["project_id"])
    sources = SourceStore(project.root).list_sources()
    return {"package_id": case["built"]["package_id"], "expected_revision": read(project.root)["revision"],
        "recipient": "synthetic-engineering-acceptance", "data_classification": "SYNTHETIC",
        "source_grants": [{"source_id": s["source_id"], "sha256": s["content_sha256"], "license": "PROJECT_SYNTHETIC_FIXTURE",
                           "permission_basis": "Explicit local synthetic engineering check"} for s in sources]}


@pytest.mark.parametrize("fixture", ["hr_case", "forestry_case"])
def test_real_service_package_to_handoff_and_download(fixture, request):
    case = request.getfixturevalue(fixture)
    result = case["run"]("modeling.handoff.export", request_for(case), "handoff")
    service = case["service"]
    job = next(j for j in service.jobs.list_project(case["project_id"]) if j.operation_id == "modeling.handoff.export")
    raw = download(service, case["principal"], case["project_id"], job.job_id)
    files = read_zip(raw)
    report = verify_handoff(files)
    assert report["status"] == "VERIFIED"
    assert result["sha256"] == digest(raw)
    assert report["native_archive_sha256"] == digest(files["native/ontology.kgop"])
    manifest = json.loads(files["manifest.json"])
    assert manifest["review_nature"] == "SYNTHETIC_ENGINEERING"
    assert json.loads(files["mapping.json"])["native_execution_policy"] == "DECLARATIVE_NOT_EXECUTED"
    assert json.loads(files["tests/cq_01.json"])["independence"] == "SESSION_FROZEN_BEFORE_PROPOSAL"
    assert json.loads(files["tests/negative_cases.json"])["status"] == "NOT_RUN"
    if os.environ.get("ZHIGOU_HANDOFF_EVIDENCE_ROOT"):
        from pathlib import Path

        from zhigou_toolchain.modeling.delivery.cover import compose, verify_cover
        from zhigou_toolchain.modeling.delivery.exchange_io import (
            atomic_file,
            json_bytes,
            write_directory,
        )
        root = Path(os.environ["ZHIGOU_HANDOFF_EVIDENCE_ROOT"]) / fixture
        root.mkdir(parents=True, exist_ok=False)
        atomic_file(root / "ontology-handoff.zip", raw)
        atomic_file(root / "ontology.kgop", files["native/ontology.kgop"])
        cover = compose(downstream=files)
        assert verify_cover(cover)["status"] == "VERIFIED"
        write_directory(root / "handoff", cover, manifest="handoff_manifest.json")
        atomic_file(root / "receipt.json", json_bytes({"result": result, "verification": report,
            "data": "SYNTHETIC_ENGINEERING", "source_job_id": job.job_id, "live_inference_calls": 0}))
    token, _ = service.tokens.create(principal_id=case["principal"].principal_id, principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="synthetic-test")
    with TestClient(create_app(service)) as client:
        response = client.get(f'/api/v1/projects/{case["project_id"]}/handoffs/{job.job_id}/archive', headers={"Authorization": "Bearer " + token})
        assert response.status_code == 200 and response.content == raw
    _, denied = service.tokens.create(principal_id="restricted", principal_type="HUMAN", permissions={"package:export", "source:read"}, project_ids={case["project_id"]}, created_by="synthetic-test")
    with pytest.raises(ServiceBoundaryError):
        service.execute(OperationRequest("modeling.handoff.export", case["project_id"], request_for(case), "denied"), denied)
    with pytest.raises(ServiceBoundaryError):
        case["run"]("modeling.handoff.export", {**request_for(case), "expected_revision": 1}, "stale-handoff")
    with pytest.raises(ServiceBoundaryError):
        case["run"]("modeling.handoff.export", {**request_for(case), "source_grants": []}, "missing-grant")


def test_service_program_trace_is_private_and_strict_v2_blocked(hr_case):  # noqa: F811
    case = hr_case
    service = case["service"]
    service.configuration = replace(service.configuration, ontology_trace_enabled=True)
    result = case["run"]("modeling.profile", {"run_id": case["ingestion"]["run_id"]}, "trace-profile")
    job = next(j for j in service.jobs.list_project(case["project_id"]) if (j.result or {}).get("agent_execution", {}).get("run_id") == result["agent_execution"]["run_id"])
    params = {"job_id": job.job_id, "batch_id": "program-only", "profile": "local"}
    exported = case["run"]("modeling.evolution.export", params, "trace-local")
    assert exported["strict_v2"] == "BLOCKED"
    with pytest.raises(ServiceBoundaryError):
        case["run"]("modeling.evolution.export", {**params, "profile": "strict-v2"}, "trace-strict")
    assert "events" not in result["agent_execution"]


def test_failed_job_keeps_controlled_trace_without_result_package(hr_case, monkeypatch):  # noqa: F811
    case = hr_case
    service = case["service"]
    service.configuration = replace(service.configuration, ontology_trace_enabled=True)
    for key in ("ZHIGOU_QWEN_MODEL", "ZHIGOU_QWEN_ENDPOINT", "ZHIGOU_QWEN_REVISION", "KG_MNP_QWEN_MODEL", "KG_MNP_QWEN_ENDPOINT", "KG_MNP_QWEN_REVISION", "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_TEXT_MODEL"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ServiceBoundaryError):
        case["run"]("modeling.scope.draft", {"run_id": case["ingestion"]["run_id"], "business_goal": "Synthetic failed model configuration", "business_rules": ["No credentials or paid calls"]}, "failed-trace")
    job = next(j for j in service.jobs.list_project(case["project_id"]) if j.operation_id == "modeling.scope.draft")
    assert job.status == "FAILED" and job.result is None
    local = case["run"]("modeling.evolution.export", {"job_id": job.job_id, "batch_id": "failed-local", "profile": "local"}, "export-failed")
    assert local["status"] == "LOCAL_DIAGNOSTIC_EXPORTED"
    export_job = next(j for j in service.jobs.list_project(case["project_id"]) if (j.result or {}).get("source_job_id") == job.job_id)
    raw = download(service, case["principal"], case["project_id"], export_job.job_id)
    # Local diagnostic ZIP has no receiver manifest and is not a fake successful run.
    import zipfile
    from io import BytesIO
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        trace = json.loads(archive.read("local-trace.json"))
        assert trace["events"][-1]["status"] == "failed"
        assert "upstream_manifest.json" not in archive.namelist()
        assert not any(e["event"] == "llm_call" for e in trace["events"])
