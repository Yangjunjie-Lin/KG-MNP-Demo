"""Freeze all source once; retain raw outcomes and do not repair a frozen run."""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tools.verify_stage_handoff import json_records, junit, run
from zhigou_toolchain.modeling.delivery.exchange_io import atomic_file, json_bytes
from zhigou_toolchain.modeling.delivery.snapshot import (
    assert_unchanged,
    source_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--full-backend", action="store_true", help="Full existing verifier, always skip paid model probe")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    snapshot = source_snapshot(ROOT)
    atomic_file(output / "source-snapshot.json", json_bytes(snapshot))
    print(json.dumps({"snapshot_id": snapshot["snapshot_id"], "head": snapshot["git_head"], "output": str(output)}), flush=True)
    checks = []
    try:
        # Test processes, not delegated agents. Core and UI are read-only with
        # respect to frozen source; all products go to separate runtime outputs.
        with ThreadPoolExecutor(max_workers=2) as pool:
            full = pool.submit(run, output, "full-backend", [sys.executable, "tools/verify_zhigou_upgrade.py",
                "--backend-only", "--workers", "4", "--skip-model-probe"], snapshot) if args.full_backend else None
            if full is None:
                checks.append(run(output, "expert-focused", [], snapshot, pytest_args=["tests/upgrade/test_expert_loop.py",
                    "tests/services/test_expert_authority.py", "tests/services/test_expert_service.py",
                    "tests/upgrade/test_step_audit.py", "tests/upgrade/test_prompt_audit.py", "tests/upgrade/test_agent_roles.py",
                    "tests/upgrade/test_evolution_delivery.py", "tests/services/test_five_stage_service.py"]))
            npm = "npm.cmd" if os.name == "nt" else "npm"
            for name in ("lint", "typecheck", "test", "build"):
                checks.append(run(output, "frontend-" + name, [npm, "--prefix", "workbench", "run", name], snapshot))
            if full:
                # Keep the prescribed four-worker backend run, but do not add
                # concurrent compiler service cases to its validator load.
                checks.append(full.result())
            cases = run(output, "expert-service-cases", [sys.executable, "-m", "tools.verify_expert_workbench", str(output / "cases"), "--pack", "both"], snapshot)
            checks.append(cases)
            if cases["exit_code"] == 0:
                receipt = json.loads((output / "cases/hr/verification.json").read_bytes())
                checks.append(run(output, "browser", [sys.executable, "tools/run_browser_verification.py", "--selected-test", "handoff.e2e.ts",
                    "--existing-upgrade-workspace", str(output / "cases/hr/upgrade-hr0"),
                    "--existing-export-job-id", receipt["export_job_id"], "--startup-timeout", "90"], snapshot))
        source_after = assert_unchanged(ROOT, snapshot)
        backend = None
        if args.full_backend:
            records = json_records(output / "checks/full-backend/command.log")
            nested = next((Path(r["evidence"]) for r in records if "evidence" in r), None)
            if nested:
                backend = {"output": str(nested), **junit(nested / "backend.xml")}
        report = {"source_snapshot_id": snapshot["snapshot_id"], "source_after": source_after, "source_unchanged": True,
            "checks": checks, "backend": backend, "raw_status": "PASS" if all(c["exit_code"] == 0 for c in checks) else "FAIL",
            "full_backend": "RUN" if args.full_backend else "NOT_RUN", "paid_calls": 0,
            "live_expert_trial": "NOT_RUN", "external_receiver": "NOT_CONTACTED", "release": "NOT_PERFORMED"}
        atomic_file(output / "verification.json", json_bytes(report))
        text = f"# 本轮冻结验证\n\nHEAD: {snapshot['git_head']}\n\n源码快照: {snapshot['snapshot_id']}\n\n原始结论: {report['raw_status']}；source_unchanged=true。\n\n"
        text += "\n".join(f"- {c['name']}: exit_code={c['exit_code']}，原始记录 checks/{c['name']}/command.log" for c in checks)
        text += "\n\n模型仅 MockTransport，专家身份/业务数据均合成。未付费、未推送/合并/发布、未进行真实业务动作。\n"
        atomic_file(output / "FINAL_REPORT.md", text.encode("utf-8"))
        print(json.dumps({"raw_status": report["raw_status"], "source_unchanged": True, "output": str(output)}), flush=True)
    except BaseException as exc:
        atomic_file(output / "ABORTED.json", json_bytes({"status": "ABORTED_NOT_QUALIFIED", "exception_type": type(exc).__name__,
            "reason": str(exc), "checks_completed": checks, "source_snapshot_id": snapshot["snapshot_id"]}))
        raise


if __name__ == "__main__":
    main()
