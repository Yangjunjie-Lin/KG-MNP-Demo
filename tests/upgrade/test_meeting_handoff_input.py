from __future__ import annotations

import asyncio
import json
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from zhigou_toolchain.jobs.worker import JobWorker
from zhigou_toolchain.modeling.delivery.exchange_io import file_rows, json_bytes
from zhigou_toolchain.modeling.delivery.meeting_input import (
    generation_files,
    validate_input,
)
from zhigou_toolchain.semantic_kernel.packaging.archive import archive_mapping_bytes
from zhigou_toolchain.services.facade import ApplicationService
from zhigou_toolchain.services.models import OperationRequest, ServiceConfiguration
from zhigou_toolchain.services.uploads import receive_upload

ROOT = Path(__file__).parents[2]


def input_files():
    with zipfile.ZipFile(ROOT / "docs/ontology/references/meeting-handoff-v2.original.zip") as archive:
        prefix = next(n[:-len("manifest.json")] for n in archive.namelist() if n.endswith("/upstream/manifest.json"))
        return {n[len(prefix):]: archive.read(n) for n in archive.namelist() if n.startswith(prefix) and not n.endswith("/")}


def rebind(files):
    manifest = json.loads(files["manifest.json"])
    manifest["files"] = file_rows({k: v for k, v in files.items() if k != "manifest.json"})
    files["manifest.json"] = json_bytes(manifest)


def test_original_input_and_generation_view():
    files = input_files()
    parsed = validate_input(files)
    assert len(parsed["sources"]) == 3
    view = generation_files(files)
    assert "acceptance_private/expected_answers.json" not in view
    assert json.loads(view["manifest.json"])["format"] == "zhigou-generation-input/1.0.0"
    broken = deepcopy(files)
    broken["sources/employees.csv"] += b"tamper"
    with pytest.raises(ValueError, match="BYTES_MISMATCH"):
        validate_input(broken)
    manifest = json.loads(files["manifest.json"])
    manifest["generation_allowlist"].append("acceptance_private/expected_answers.json")
    broken = {**files, "manifest.json": json_bytes(manifest)}
    with pytest.raises(ValueError, match="PRIVATE_INPUT"):
        validate_input(broken)


def test_real_meeting_input_upload_native_ingestion(tmp_path):
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    _, principal = service.tokens.create(principal_id="synthetic-input-owner", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="synthetic-test")
    project = service.execute(OperationRequest("project.create", parameters={"name": "meeting-input", "domain_pack": "hr", "domain_pack_version": "0.1.0"}), principal).payload["project_id"]
    async def chunks():
        yield archive_mapping_bytes(input_files())
    accepted = asyncio.run(receive_upload(service, project, principal, chunks(), filename="input.zip", media_type="application/zip", idempotency_key="meeting-input", operation="modeling.handoff.import"))
    job = JobWorker(service.jobs, service).run_once("meeting-input")
    assert job.job_id == accepted.job_id and job.status == "SUCCEEDED", job.error
    result = job.result
    assert result["approval"] == "NOT_GRANTED"
    assert result["run"]["run_id"].startswith("urn:kg-mnp:")
    assert len(result["binding"]["source_id_map"]) == 3
    assert result["binding"]["native_evidence_ids"]
    assert "expected_answers" not in json.dumps(result)
