from __future__ import annotations

import json
from pathlib import Path

from prompt03_support import run_cli

from kg_mnp.ingestion.source_store import SourceStore


def _batch(workspace: Path, tmp_path: Path) -> str:
    source = tmp_path / "sample.txt"
    source.write_text("evidence\n", encoding="utf-8")
    store = SourceStore(workspace)
    source_id = store.add_file(source).source["source_id"]
    return store.create_batch([source_id])["batch_id"]


def test_ingest_plan_run_status_validate_inspect_and_retry_cli(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    batch_id = _batch(prompt03_workspace, tmp_path)
    planned = run_cli(
        "ingest", "plan", str(prompt03_workspace), "--batch", batch_id, "--json"
    )
    assert planned.returncode == 0, planned.stdout + planned.stderr
    plan = json.loads(planned.stdout)["result"]
    assert plan["status"] == "READY"
    executed = run_cli(
        "ingest", "run", str(prompt03_workspace), "--plan", plan["plan_id"], "--json"
    )
    assert executed.returncode == 0, executed.stdout + executed.stderr
    run_id = json.loads(executed.stdout)["result"]["run"]["run_id"]
    for operation in ("status", "validate", "inspect"):
        result = run_cli(
            "ingest", operation, str(prompt03_workspace), run_id, "--json"
        )
        assert result.returncode == 0, result.stdout + result.stderr
    retry = run_cli(
        "ingest", "retry-plan", str(prompt03_workspace), run_id, "--json"
    )
    assert retry.returncode == 0
    assert json.loads(retry.stdout)["result"]["changed"] is False


def test_ingest_batch_shortcut_and_unresolved_video_cli(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    batch_id = _batch(prompt03_workspace, tmp_path)
    executed = run_cli(
        "ingest", "run", str(prompt03_workspace), "--batch", batch_id, "--json"
    )
    assert executed.returncode == 0
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42\xff")
    store = SourceStore(prompt03_workspace)
    source_id = store.add_file(video).source["source_id"]
    video_batch = store.create_batch([source_id])["batch_id"]
    unresolved = run_cli(
        "ingest", "plan", str(prompt03_workspace), "--batch", video_batch, "--json"
    )
    assert unresolved.returncode == 12
    payload = json.loads(unresolved.stdout)
    assert payload["status"] == "UNRESOLVED"
    assert "MISSING_TRANSCRIPTION_OR_VIDEO_PROVIDER" in {
        item["code"] for item in payload["result"]["issues"]
    }
