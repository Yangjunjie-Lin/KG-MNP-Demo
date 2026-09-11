"""Same-source final verification driver; individual checks never imply release."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from xml.etree import ElementTree

from evaluate_research import fingerprint

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--frontend-only", action="store_true", help="explicit partial verification, never full backend acceptance")
    scope.add_argument("--backend-only", action="store_true", help="full backend without rebuilding or disturbing an active browser run")
    args = parser.parse_args()
    output = ROOT / "runtime_reports" / ("zhigou-verification-" + uuid4().hex)
    output.mkdir(parents=True)
    before = fingerprint()
    print(json.dumps({"evidence": str(output), "source_digest": before["digest"]}), flush=True)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    commands = [("ruff", [sys.executable, "-m", "ruff", "check", ".", "--no-cache"]),
                ("types", [sys.executable, "tools/check_types.py"]),
                ("frontend-lint", [npm, "--prefix", "workbench", "run", "lint"]),
                ("frontend-tests", [npm, "--prefix", "workbench", "test"]),
                ("frontend-build", [npm, "--prefix", "workbench", "run", "build"])]
    if not args.frontend_only:
        commands.append(("backend", [sys.executable, "-m", "pytest", "-p", "xdist.plugin", "-p", "tests.verification_receipts",
            "-n", str(args.workers), "--dist", "loadfile", "--tb=short", f"--basetemp={output / 'pytest-temp'}", f"--junitxml={output / 'backend.xml'}"]))
    if args.backend_only:
        commands = [(name, command) for name, command in commands if not name.startswith("frontend-")]
    else:
        commands.append(("browser", [sys.executable, "tools/run_browser_verification.py"]))
    commands.append(("model-probe", [sys.executable, "tools/probe_upgrade_models.py"]))
    records = []
    required_nodes = None
    for name, command in commands:
        started = perf_counter()
        print("START", name, flush=True)
        environment = {**os.environ, "PYTHONUTF8": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "KG_MNP_RECEIPT_ROOT": str(output)}
        if os.name == "nt":
            # Nested fixture repositories inherit process-only long-path
            # support; preserve existing Git config entries and global config.
            index = int(environment.get("GIT_CONFIG_COUNT", "0"))
            environment[f"GIT_CONFIG_KEY_{index}"] = "core.longpaths"
            environment[f"GIT_CONFIG_VALUE_{index}"] = "true"
            environment["GIT_CONFIG_COUNT"] = str(index + 1)
        if name == "backend":
            collection = output / "collection"
            collection.mkdir()
            with (collection / "command.log").open("wb") as stream:
                collected = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-p", "tests.verification_receipts"], cwd=ROOT,
                    env={**environment, "KG_MNP_RECEIPT_ROOT": str(collection)}, stdout=stream, stderr=subprocess.STDOUT, check=False)
            records.append({"check": "collection", "exit_code": collected.returncode})
            required_nodes = json.loads((collection / "collection.json").read_bytes()) if (collection / "collection.json").exists() else []
        with (output / (name + ".log")).open("wb") as stream:
            completed = subprocess.run(command, cwd=ROOT, env=environment, stdout=stream, stderr=subprocess.STDOUT, check=False)
        records.append({"check": name, "command": command, "exit_code": completed.returncode, "duration_seconds": perf_counter() - started})
        print("END", name, completed.returncode, flush=True)
    after = fingerprint()
    junit = output / "backend.xml"
    cases = []
    if junit.exists():
        for row in ElementTree.parse(junit).findall(".//testcase"):
            outcome = "ERROR" if row.find("error") is not None else "FAIL" if row.find("failure") is not None else "SKIP" if row.find("skipped") is not None else "PASS"
            cases.append({"class": row.get("classname"), "test": row.get("name"), "outcome": outcome})
    report = {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "source": before, "source_unchanged": before == after, "checks": records, "test_cases": cases,
        "verification_scope": "FRONTEND_PARTIAL" if args.frontend_only else "FULL_BACKEND" if args.backend_only else "FULL_BACKEND_AND_BROWSER_ATTEMPT",
        "research_metrics": "INSUFFICIENT_EVIDENCE", "remote_rename": "NOT_EXECUTED", "formal_release_qualified": False}
    report["git_longpaths"] = "PROCESS_ONLY" if os.name == "nt" else "NOT_APPLICABLE"
    if required_nodes is not None:
        executed = {row["nodeid"] for row in json.loads((output / "reports.json").read_bytes())} if (output / "reports.json").exists() else set()
        report["collection"] = {"required": len(required_nodes), "executed": len(executed), "missing": sorted(set(required_nodes) - executed),
            "extra": sorted(executed - set(required_nodes)), "complete": bool(required_nodes) and set(required_nodes) == executed}
    (output / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(output, flush=True)
    return int(before != after or any(r["exit_code"] for r in records) or (required_nodes is not None and not report["collection"]["complete"]))


if __name__ == "__main__":
    raise SystemExit(main())
