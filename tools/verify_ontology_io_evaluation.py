"""Preserve actual command logs and source identity for this incremental audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from zhigou_toolchain.ontology_io.cli import save
from zhigou_toolchain.ontology_io.provenance import runtime_versions, source_identity

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    before = source_identity(ROOT)
    save(output / "source-before.json", before)
    status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT)
    (output / "worktree-status.txt").write_bytes(status)
    (output / "worktree.diff").write_bytes(subprocess.check_output(["git", "diff", "--", "src/zhigou_toolchain/ontology_io", "config/ontology_io", "tools", "tests/upgrade"], cwd=ROOT))
    commands = [
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "tools/check_types.py"],
        [sys.executable, "tools/evaluate_research.py", "--suite", "ontology-io-engineering"],
        [sys.executable, "-m", "pytest", "tests/upgrade/test_ontology_io_extended.py", "--tb=short", f"--junitxml={output / 'extended.xml'}"],
    ]
    rows = []
    for index, command in enumerate(commands):
        started = perf_counter()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
        path = output / f"command-{index}.log"
        path.write_bytes(result.stdout + result.stderr)
        rows.append({"command": command, "exit_code": result.returncode, "seconds": perf_counter() - started,
            "log": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        save(output / "commands.json", rows)
        print(json.dumps({"index": index, "exit_code": result.returncode}), flush=True)
    after = source_identity(ROOT)
    save(output / "source-after.json", after)
    report = {"status": "ENGINEERING_CHECKS_ONLY", "source_unchanged": before == after,
        "commands": rows, "runtime": runtime_versions(), "research_score": None, "experiment_complete": False}
    save(output / "verification.json", report)
    print(output, flush=True)
    return int(any(r["exit_code"] for r in rows) or before != after)


if __name__ == "__main__":
    raise SystemExit(main())
