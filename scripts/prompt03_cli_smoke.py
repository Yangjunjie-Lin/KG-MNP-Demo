"""Exercise the public Prompt 3 CLI against every honestly supported format."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from generate_ingestion_examples import generate

ROOT = Path(__file__).resolve().parents[1]
TEXT_FIXTURES = ROOT / "examples" / "ingestion" / "minimal-project"
DEFAULT_WORKSPACE = ROOT / "runtime_outputs" / "prompt-03-cli-smoke"
DEFAULT_BINARY_FIXTURES = ROOT / "runtime_outputs" / "prompt-03-examples"


def _invoke(
    *arguments: str,
    accepted: tuple[int, ...] = (0,),
    parse_json: bool = True,
) -> Any:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        ("kg-mnp", *arguments),
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=120,
    )
    if completed.returncode not in accepted:
        raise RuntimeError(
            f"kg-mnp {' '.join(arguments)} returned {completed.returncode}: "
            f"{completed.stderr or completed.stdout}"
        )
    return json.loads(completed.stdout) if parse_json else completed.stdout.strip()


def _prepare_runtime_fixtures(binary_root: Path) -> dict[str, Path]:
    generate(binary_root)
    tsv = binary_root / "sample.tsv"
    tsv.write_text("record_id\tlabel\tvalue\nsample-001\tcanopy-cover\t42.50\n", encoding="utf-8")
    video = binary_root / "unsupported-video.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom\xff")
    return {
        "video": video,
        "txt": TEXT_FIXTURES / "sample.txt",
        "markdown": TEXT_FIXTURES / "sample.md",
        "json": TEXT_FIXTURES / "sample.json",
        "csv": TEXT_FIXTURES / "sample.csv",
        "tsv": tsv,
        "xlsx": binary_root / "sample.xlsx",
        "docx": binary_root / "sample.docx",
        "pdf": binary_root / "sample.pdf",
        "png": binary_root / "sample.png",
        "wav": binary_root / "sample.wav",
    }


def _plugin_smokes(records: list[dict[str, Any]]) -> None:
    records.append({"command": "plugin list", "output": _invoke("plugin", "list", parse_json=False)})
    for arguments in (
        ("plugin", "list", "--json"),
        ("plugin", "doctor", "--json"),
        ("plugin", "validate", "plain-text-parser", "--json"),
        ("plugin", "snapshot", "plain-text-parser", "--json"),
        ("plugin", "conformance", "plain-text-parser", "--json"),
    ):
        records.append({"command": " ".join(arguments[:-1]), "output": _invoke(*arguments)})


def _ingest_fixture(
    workspace: Path,
    label: str,
    source: Path,
    records: list[dict[str, Any]],
) -> None:
    workspace_arg = str(workspace)
    added = _invoke("source", "add", workspace_arg, str(source), "--json")
    source_id = added["result"]["source"]["source_id"]
    batched = _invoke("source", "batch-create", workspace_arg, source_id, "--json")
    batch_id = batched["result"]["batch_id"]
    planned = _invoke(
        "ingest",
        "plan",
        workspace_arg,
        "--batch",
        batch_id,
        "--json",
        accepted=(0, 12),
    )
    plan = planned["result"]
    entry: dict[str, Any] = {
        "format": label,
        "source_id": source_id,
        "batch_id": batch_id,
        "plan_id": plan["plan_id"],
        "plan_status": plan["status"],
        "plan_issues": plan["issues"],
    }
    if label == "video":
        if plan["status"] != "UNRESOLVED":
            raise RuntimeError("unsupported video did not remain unresolved")
        missing_codes = {
            "MISSING_PROVIDER",
            "MISSING_TRANSCRIPTION_OR_VIDEO_PROVIDER",
        }
        if not any(issue["code"] in missing_codes for issue in plan["issues"]):
            raise RuntimeError("unsupported video did not report a missing provider")
        entry["fabricated_items"] = 0
        records.append(entry)
        return

    executed = _invoke(
        "ingest",
        "run",
        workspace_arg,
        "--plan",
        plan["plan_id"],
        "--json",
        accepted=(0, 14),
    )
    run = executed["result"]["run"]
    dataset_id = executed["result"]["dataset_id"]
    run_id = run["run_id"]
    entry.update(
        {
            "run_id": run_id,
            "run_status": run["status"],
            "quality_gate": executed["result"]["quality_report"]["gate_status"],
            "dataset_id": dataset_id,
        }
    )
    if label == "txt":
        for operation in ("status", "validate", "inspect"):
            _invoke("ingest", operation, workspace_arg, run_id, "--json")
        inspected = _invoke("ir", "inspect", workspace_arg, dataset_id, "--json")
        dataset = inspected["result"]
        _invoke("ir", "validate", workspace_arg, dataset_id, "--json")
        _invoke("ir", "sources", workspace_arg, dataset_id, "--json")
        first_item = dataset["items"][0]["item_id"]
        traced = _invoke("ir", "trace", workspace_arg, first_item, "--json")
        if not traced["result"]["source_blob_hashes"]:
            raise RuntimeError("TXT trace did not close at a source blob")
        entry.update(
            {
                "item_count": len(dataset["items"]),
                "trace_item_id": first_item,
                "trace_blob_hashes": traced["result"]["source_blob_hashes"],
            }
        )
    records.append(entry)


def run(workspace: Path, binary_root: Path) -> dict[str, Any]:
    if workspace.exists():
        raise RuntimeError(f"refusing to overwrite existing smoke workspace: {workspace}")
    fixtures = _prepare_runtime_fixtures(binary_root)
    initialized = _invoke(
        "workspace",
        "init",
        str(workspace),
        "--project-id",
        "prompt03-cli-smoke",
        "--project-version",
        "0.3.0",
        "--display-name",
        "Prompt 3 CLI Smoke",
        "--domain-pack",
        "minimal",
        "--domain-pack-version",
        "0.1.0",
        "--domain-packs-root",
        str(ROOT / "domain_packs"),
        "--json",
    )
    records: list[dict[str, Any]] = []
    _plugin_smokes(records)
    for label, source in fixtures.items():
        _ingest_fixture(workspace, label, source, records)
        if label == "txt":
            source_id = records[-1]["source_id"]
            _invoke("source", "list", str(workspace), "--json")
            _invoke("source", "inspect", str(workspace), source_id, "--json")
            _invoke("source", "verify", str(workspace), source_id, "--json")
    return {"workspace": initialized["status"], "records": records}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--binary-fixtures", type=Path, default=DEFAULT_BINARY_FIXTURES)
    arguments = parser.parse_args()
    result = run(arguments.workspace.resolve(), arguments.binary_fixtures.resolve())
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
