"""Retain authorized synthetic service artifacts; no production credentials stored."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from zhigou_toolchain.api.app import create_app
from zhigou_toolchain.modeling.delivery.cover import compose, verify_cover
from zhigou_toolchain.modeling.delivery.exchange_io import (
    atomic_file,
    digest,
    json_bytes,
)
from zhigou_toolchain.modeling.delivery.handoff import verify_handoff
from zhigou_toolchain.semantic_kernel.packaging.archive import archive_mapping_bytes


def retain_stage_case(case, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    service, project = case["service"], case["project_id"]
    token, principal = service.tokens.create(principal_id="synthetic-stage-transfer", principal_type="HUMAN",
        permissions={"*"}, project_ids={project}, created_by="explicit-synthetic-engineering-transfer")
    try:
        with TestClient(create_app(service)) as client:
            response = client.get(f'/api/v1/projects/{project}/handoffs/{case["export_job"].job_id}/archive', headers={"Authorization": "Bearer " + token})
            assert response.status_code == 200 and response.content == case["raw"]
        env = {**os.environ, "ZHIGOU_TOKEN": token}
        env.pop("KG_MNP_TOKEN", None)
        cli = subprocess.run([sys.executable, "-m", "zhigou_toolchain.modeling.delivery.cli", "export-handoff", str(output / "cli-same-task.zip"),
            "--workspace", str(service.root), "--project-id", project, "--job-id", case["export_job"].job_id], env=env, capture_output=True, check=False)
        atomic_file(output / "cli.log", cli.stdout + cli.stderr)
        assert cli.returncode == 0 and (output / "cli-same-task.zip").read_bytes() == case["raw"]
    finally:
        service.tokens.revoke(principal.token_id)
    atomic_file(output / "ontology-handoff.zip", case["raw"])
    atomic_file(output / "ontology.kgop", case["files"]["native/ontology.kgop"])
    combined = compose(downstream=case["files"], diagnostic=case["diagnostic"])
    assert verify_cover(combined)["status"] == "VERIFIED"
    combined_raw = archive_mapping_bytes(combined)
    atomic_file(output / "ontology-combined.zip", combined_raw)
    for name, raw in case["diagnostic"].items():
        atomic_file(output / "diagnostics" / name, raw)
    verification = {"data_origin": "NEW_SYNTHETIC_SERVICE_CHAIN", "mode": "DETERMINISTIC", "live_model_calls": 0,
        "project_id": project, "export_job_id": case["export_job"].job_id, "export_receipt": case["receipt"],
        "negative_receipt": case["negative_receipt"], "verification": verify_handoff(case["files"], trusted_receipt=case["receipt"]),
        "same_task_transport": {"api_sha256": digest(case["raw"]), "cli_sha256": digest(case["raw"]), "size_bytes": len(case["raw"])},
        "real_human_assessment": "NOT_PERFORMED", "receiver_status": "NOT_CONTACTED"}
    verification["combined_archive"] = {"name": "ontology-combined.zip", "sha256": digest(combined_raw), "size_bytes": len(combined_raw)}
    atomic_file(output / "verification.json", json_bytes(verification))
    atomic_file(output / "workspace-reference.json", json_bytes({"workspace": str(service.root), "export_job_id": case["export_job"].job_id}))
    return verification


def case_files(root):
    root = Path(root)
    files = {n: (root / n).read_bytes() for n in ("ontology-handoff.zip", "verification.json")}
    files.update({"diagnostics/" + p.name: p.read_bytes() for p in (root / "diagnostics").iterdir() if p.is_file()})
    return files
