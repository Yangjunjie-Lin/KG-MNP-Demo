"""Run independent engineering suites, preserving outcomes and source identity."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    "framework": ["tests/upgrade/test_full_chain.py", "-k", "forestry"],
    "ingestion": ["tests/services/test_source_workflow.py", "tests/services/test_mixed_source_workflow.py", "-k", "not compilation"],
    "ontology": ["tests/upgrade/test_full_chain.py", "-k", "hr"],
    "evolution": ["tests/upgrade/test_guards.py", "tests/upgrade/test_full_chain.py", "-k", "forestry or unknown"],
    "safety": ["tests/upgrade/test_guards.py", "tests/services/test_browser_sessions.py", "tests/services/test_core_fencing.py"],
}


def fingerprint():
    files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    selected = {}
    for name in sorted(set(files) - {""}):
        path = ROOT / name
        if path.is_file() and (name.startswith(("src/", "tests/", "tools/", "scripts/", ".github/", "workbench/src/", "workbench/tests/", "domain_packs/")) or name in {"pyproject.toml", "setup.py", "MANIFEST.in", "requirements-dev.lock", "pyrightconfig.json", "workbench/package.json", "workbench/package-lock.json"}):
            selected[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest()
    return {"digest": digest, "files": selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=[*SUITES, "all"], default="all")
    args = parser.parse_args()
    output = ROOT / "runtime_reports" / ("research-" + uuid4().hex)
    output.mkdir(parents=True)
    before = fingerprint()
    reports = []
    selected = SUITES if args.suite == "all" else {args.suite: SUITES[args.suite]}
    for name, selectors in selected.items():
        started = perf_counter()
        command = [sys.executable, "-m", "pytest", *selectors, "--tb=short", f"--junitxml={output / (name + '.xml')}"]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
        (output / (name + ".log")).write_bytes(result.stdout + result.stderr)
        reports.append({"suite": name, "command": command, "exit_code": result.returncode, "duration_seconds": perf_counter() - started})
        print(name, result.returncode, flush=True)
    after = fingerprint()
    report = {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "source": before, "source_unchanged": before == after, "suites": reports,
        "research_metrics": "INSUFFICIENT_EVIDENCE", "environment": "Windows local synthetic engineering tests",
        "not_a_claim": "LIVE inference, real expert approval, production deployment or numerical research attainment"}
    (output / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(output)
    return int(any(r["exit_code"] for r in reports) or before != after)


if __name__ == "__main__":
    raise SystemExit(main())
