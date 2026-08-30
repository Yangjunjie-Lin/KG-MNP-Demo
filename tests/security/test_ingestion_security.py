from __future__ import annotations

import json
from pathlib import Path

import pytest

from kg_mnp.ingestion.errors import ArtifactTamperedError, IngestionPlanError
from kg_mnp.ingestion.executor import execute_ingestion_plan
from kg_mnp.ingestion.planner import create_ingestion_plan, load_ingestion_plan
from kg_mnp.ingestion.source_store import SourceStore
from kg_mnp.ingestion.transaction import IngestionTransaction, WorkspaceOperationLock


def _plan(workspace: Path, tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text("evidence", encoding="utf-8")
    store = SourceStore(workspace)
    registered = store.add_file(source).source
    batch = store.create_batch([registered["source_id"]])
    return create_ingestion_plan(workspace, batch_id=batch["batch_id"])


def test_external_plan_path_and_tampered_plan_are_rejected(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    planned = _plan(prompt03_workspace, tmp_path)
    external = tmp_path / "external-plan.json"
    external.write_bytes(planned.path.read_bytes())
    with pytest.raises(IngestionPlanError, match="external"):
        load_ingestion_plan(prompt03_workspace, external)
    document = json.loads(planned.path.read_bytes())
    document["status"] = "INVALID"
    planned.path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="mismatch"):
        load_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])


def test_partial_formal_run_and_artifact_overwrite_are_rejected(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    planned = _plan(prompt03_workspace, tmp_path)
    from kg_mnp.contracts.canonical import stable_urn

    run_id = stable_urn(
        "ingestion-run",
        {
            "project_lock_id": planned.plan["project_lock_id"],
            "source_batch_id": planned.plan["source_batch_id"],
            "ingestion_plan_id": planned.plan["plan_id"],
            "plugin_snapshot_ids": sorted(
                item["snapshot_id"] for item in planned.plan["plugin_snapshots"]
            ),
            "execution_profile": "KG-MNP Deterministic Ingestion Execution v1",
        },
    )
    run_hash = run_id.rsplit(":", 1)[-1]
    partial = prompt03_workspace / "artifacts" / "evidence" / run_hash
    partial.mkdir(parents=True)
    with pytest.raises(ArtifactTamperedError, match="partial"):
        execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])
    partial.rmdir()
    transaction = IngestionTransaction(prompt03_workspace, run_hash)
    transaction.mapping["build"].mkdir(parents=True)
    with transaction, pytest.raises(ArtifactTamperedError, match="partial"):
        transaction.commit()
    assert not transaction.staging.exists()


def test_lock_is_conservative_and_does_not_delete_replaced_owner(
    prompt03_workspace: Path,
) -> None:
    lock = WorkspaceOperationLock(prompt03_workspace, "ingestion")
    lock.__enter__()
    lock.path.write_text(
        json.dumps({"pid": 999999, "operation": "ingestion", "nonce": "replacement"}),
        encoding="utf-8",
    )
    lock.__exit__(None, None, None)
    assert lock.path.exists()
    lock.path.unlink()


def test_invalid_existing_artifact_manifest_is_reported_as_tamper(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    planned = _plan(prompt03_workspace, tmp_path)
    result = execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])
    run_hash = result.run["run_id"].rsplit(":", 1)[-1]
    manifest = (
        prompt03_workspace
        / "artifacts"
        / "evidence"
        / run_hash
        / "artifact-manifest.json"
    )
    manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(ArtifactTamperedError, match="invalid artifact manifest"):
        execute_ingestion_plan(prompt03_workspace, planned.plan["plan_id"])
