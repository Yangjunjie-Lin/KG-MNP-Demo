from __future__ import annotations

import asyncio
import json
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from zhigou_toolchain.jobs.worker import JobWorker
from zhigou_toolchain.modeling.delivery.exchange_io import digest, file_rows, json_bytes
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
    import_input_case(tmp_path, input_files())


def import_input_case(tmp_path, files):
    """Also used by the frozen verifier for an explicitly supplied upstream ZIP."""
    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    _, principal = service.tokens.create(principal_id="synthetic-input-owner", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="synthetic-test")
    project = service.execute(OperationRequest("project.create", parameters={"name": "meeting-input", "domain_pack": "hr", "domain_pack_version": "0.1.0"}), principal).payload["project_id"]
    async def chunks():
        yield archive_mapping_bytes(files)
    accepted = asyncio.run(receive_upload(service, project, principal, chunks(), filename="input.zip", media_type="application/zip", idempotency_key="meeting-input", operation="modeling.handoff.import"))
    job = JobWorker(service.jobs, service).run_once("meeting-input")
    assert job.job_id == accepted.job_id and job.status == "SUCCEEDED", job.error
    result = job.result
    assert result["approval"] == "NOT_GRANTED"
    assert result["run"]["run_id"].startswith("urn:kg-mnp:")
    assert len(result["binding"]["source_id_map"]) == 3
    assert result["binding"]["native_evidence_ids"]
    assert "expected_answers" not in json.dumps(result)
    return result


@pytest.mark.parametrize("keep", ["records", "texts"])
def test_records_and_text_are_conditional(keep):
    files = input_files()
    manifest = json.loads(files["manifest.json"])
    locators = json.loads(files["source_locator.json"])
    removed = "text_blocks.json" if keep == "records" else "records.json"
    allowed_kinds = {"record", "record_field"} if keep == "records" else {"char_range"}
    locators["evidence"] = [e for e in locators["evidence"] if e["locator"]["kind"] in allowed_kinds]
    sources = {e["source_ref"] for e in locators["evidence"]}
    excluded = {s["file"] for s in locators["sources"] if s["source_id"] not in sources} | {removed}
    locators["sources"] = [s for s in locators["sources"] if s["source_id"] in sources]
    files = {n: raw for n, raw in files.items() if n not in excluded}
    manifest["generation_allowlist"] = [n for n in manifest["generation_allowlist"] if n not in excluded]
    quality = json.loads(files["quality_report.json"])
    quality["checked_files"] = [r for r in quality.get("checked_files", []) if r["path"] not in excluded]
    files.update({"manifest.json": json_bytes(manifest), "quality_report.json": json_bytes(quality), "source_locator.json": json_bytes(locators)})
    # This is a newly synthesized conditional fixture, not a rewritten original.
    quality["checked_files"] = [{**r, "sha256": digest(files[r["path"]])} for r in quality["checked_files"]]
    files["quality_report.json"] = json_bytes(quality)
    rebind(files)
    parsed = validate_input(files)
    assert parsed["records"]["records"] if keep == "records" else parsed["texts"]["text_blocks"]


@pytest.mark.parametrize("change,code", [("quality", "QUALITY_REVIEW"), ("unicode", "LOCATOR"), ("license", "LICENSE"),
    ("lock", "LOCK_REQUIRED"), ("private-case", "PRIVATE_INPUT"), ("unclassified", "CLASSIFICATION")])
def test_new_input_negatives(change, code):
    files = input_files()
    manifest = json.loads(files["manifest.json"])
    if change == "quality":
        doc = json.loads(files["quality_report.json"])
        doc["quarantined_record_ids"] = ["synthetic"]
        files["quality_report.json"] = json_bytes(doc)
    elif change == "unicode":
        doc = json.loads(files["source_locator.json"])
        item = next(e for e in doc["evidence"] if e["locator"]["kind"] == "char_range")
        item["locator"]["end"] = 10000  # byte/character confusion must fail
        files["source_locator.json"] = json_bytes(doc)
        # Advance only the synthetic checksum so the locator gate is reached.
        quality = json.loads(files["quality_report.json"])
        quality["checked_files"] = [{**r, "sha256": digest(files[r["path"]])} for r in quality["checked_files"]]
        files["quality_report.json"] = json_bytes(quality)
    elif change == "license":
        doc = json.loads(files["imports.lock.json"])
        doc["license"] = {}
        files["imports.lock.json"] = json_bytes(doc)
    elif change == "lock":
        files.pop("imports.lock.json")
        manifest["generation_allowlist"].remove("imports.lock.json")
    elif change == "private-case":
        files["Acceptance_Private/hidden.json"] = b'{}'
        manifest["generation_allowlist"].append("Acceptance_Private/hidden.json")
    else:
        manifest["generation_allowlist"].remove("records.json")
    files["manifest.json"] = json_bytes(manifest)
    rebind(files)
    with pytest.raises(ValueError, match=code):
        validate_input(files)
