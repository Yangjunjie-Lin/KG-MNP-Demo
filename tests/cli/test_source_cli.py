from __future__ import annotations

import json
from pathlib import Path

from prompt03_support import run_cli


def test_source_add_list_inspect_verify_and_batch_cli(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("evidence\n", encoding="utf-8")
    added = run_cli("source", "add", str(prompt03_workspace), str(source), "--json")
    assert added.returncode == 0, added.stdout + added.stderr
    source_id = json.loads(added.stdout)["result"]["source"]["source_id"]
    listing = run_cli("source", "list", str(prompt03_workspace), "--json")
    assert listing.returncode == 0
    assert [item["source_id"] for item in json.loads(listing.stdout)["result"]] == [source_id]
    inspected = run_cli(
        "source", "inspect", str(prompt03_workspace), source_id, "--json"
    )
    assert inspected.returncode == 0
    assert json.loads(inspected.stdout)["result"]["source_id"] == source_id
    verified = run_cli("source", "verify", str(prompt03_workspace), source_id, "--json")
    assert verified.returncode == 0
    assert json.loads(verified.stdout)["result"]["valid"] is True
    batch = run_cli(
        "source", "batch-create", str(prompt03_workspace), source_id, "--json"
    )
    assert batch.returncode == 0
    batch_id = json.loads(batch.stdout)["result"]["batch_id"]
    batch_inspect = run_cli(
        "source", "batch-inspect", str(prompt03_workspace), batch_id, "--json"
    )
    assert batch_inspect.returncode == 0
    assert json.loads(batch_inspect.stdout)["result"]["sources"] == [source_id]


def test_source_recursive_directory_and_error_cli(
    prompt03_workspace: Path, tmp_path: Path
) -> None:
    directory = tmp_path / "inputs"
    (directory / "nested").mkdir(parents=True)
    (directory / "a.txt").write_text("a", encoding="utf-8")
    (directory / "nested" / "b.txt").write_text("b", encoding="utf-8")
    added = run_cli(
        "source",
        "add",
        str(prompt03_workspace),
        str(directory),
        "--recursive",
        "--json",
    )
    assert added.returncode == 0
    assert len(json.loads(added.stdout)["result"]) == 2
    missing = run_cli(
        "source",
        "inspect",
        str(prompt03_workspace),
        "urn:kg-mnp:source:" + "0" * 64,
        "--json",
    )
    assert missing.returncode == 11
    assert "Traceback" not in missing.stdout + missing.stderr
