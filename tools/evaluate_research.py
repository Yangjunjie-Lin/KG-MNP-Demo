"""Run independent engineering suites, preserving outcomes and source identity."""
from __future__ import annotations

import argparse
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
    "ontology-io-engineering": ["tests/upgrade/test_agent_roles.py", "tests/upgrade/test_model_assistance.py",
        "tests/upgrade/test_v3_delivery.py", "tests/upgrade/test_native_delivery.py", "tests/upgrade/test_ontology_io.py",
        "tests/upgrade/test_ontology_io_integrity.py", "tests/upgrade/test_oskgc_native.py", "tests/upgrade/test_cq4oe_input.py", "tests/services/test_ontology_io_report.py",
        "tests/services/test_five_stage_service.py", "tests/services/test_core_fencing.py"],
}


def fingerprint():
    from zhigou_toolchain.ontology_io.provenance import source_fingerprint
    return source_fingerprint(ROOT)


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
    if len(sys.argv) > 1 and sys.argv[1] == "ontology-io":
        from zhigou_toolchain.ontology_io.cli import main as ontology_io_main
        ontology_io_main(sys.argv[2:])
    else:
        raise SystemExit(main())
