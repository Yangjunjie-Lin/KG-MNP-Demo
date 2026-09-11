"""Publish redacted copies of explicitly selected runs, retaining every outcome.

Raw receipts stay in runtime_reports. Published copies are not byte-identical raw
receipts: absolute machine paths and repeated source-file inventories are omitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def redact(value):
    if isinstance(value, dict):
        return {key: ({"digest": item["digest"], "file_count": len(item.get("files", {}))} if key == "source" and isinstance(item, dict) and "digest" in item
            else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = value.replace(str(ROOT), "{REPO_ROOT}").replace(ROOT.as_posix(), "{REPO_ROOT}")
        if re.match(r"^[A-Za-z]:[/\\]", value):
            return "{LOCAL_MODEL_OR_RUNTIME}/" + Path(value).name
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = []
    for path in args.runs:
        path = path.resolve(strict=True)
        path.relative_to(ROOT / "runtime_reports")
        raw = path.read_bytes()
        report = json.loads(raw)
        results.append({"raw_report": path.relative_to(ROOT).as_posix(), "raw_sha256": hashlib.sha256(raw).hexdigest(), "report": redact(report)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output = {"schema_version": "1.0.0", "artifact_kind": "REDACTED_ENGINEERING_RUNS",
        "qualification": "Synthetic real-model execution, not expert-labelled research accuracy or provider weight/vLLM attestation.",
        "redaction": "Machine paths replaced; source manifests summarized. Raw report digests identify retained originals.", "runs": results}
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"runs": len(results), "statuses": [r["report"].get("status", "UNSPECIFIED") for r in results]}))


if __name__ == "__main__":
    main()
