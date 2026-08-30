from __future__ import annotations

import json
from pathlib import Path

from prompt03_support import run_cli

from kg_mnp.ingestion.executor import execute_ingestion_plan
from kg_mnp.ingestion.planner import create_ingestion_plan
from kg_mnp.ingestion.source_store import SourceStore


def test_ir_inspect_validate_sources_and_full_trace_cli(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "sample.json"
    source.write_bytes(b'{"value":1.25}')
    store = SourceStore(prompt03_workspace)
    source_id = store.add_file(source).source["source_id"]
    batch = store.create_batch([source_id])
    plan = create_ingestion_plan(prompt03_workspace, batch_id=batch["batch_id"])
    executed = execute_ingestion_plan(prompt03_workspace, plan.plan["plan_id"])
    dataset_id = executed.dataset["dataset_id"]
    for operation in ("inspect", "validate", "sources"):
        result = run_cli("ir", operation, str(prompt03_workspace), dataset_id, "--json")
        assert result.returncode == 0, result.stdout + result.stderr
    item_id = next(
        item["item_id"] for item in executed.dataset["items"] if item["item_kind"] == "scalar-field"
    )
    traced = run_cli("ir", "trace", str(prompt03_workspace), item_id, "--json")
    assert traced.returncode == 0, traced.stdout + traced.stderr
    trace = json.loads(traced.stdout)["result"]
    assert trace["kg_ir_item"]["item_id"] == item_id
    assert trace["evidence_records"]
    assert trace["source_locators"]
    assert trace["source_assets"]
    assert trace["source_blob_hashes"] == [
        trace["source_assets"][0]["content_sha256"]
    ]
    assert trace["plugin_snapshots"]
    assert trace["transformation_records"]


def test_ir_missing_subject_returns_stable_error(prompt03_workspace: Path) -> None:
    result = run_cli(
        "ir",
        "inspect",
        str(prompt03_workspace),
        "urn:kg-mnp:kg-ir-dataset:" + "0" * 64,
        "--json",
    )
    assert result.returncode == 13
    assert "Traceback" not in result.stdout + result.stderr
