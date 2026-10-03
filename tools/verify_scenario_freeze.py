"""Freeze current source/resources/tests, then retain every raw verification result."""
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
    parser.add_argument("--full-backend", action="store_true", help="Original full verifier; always skips paid model probes")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    snapshot = source_snapshot(ROOT)
    atomic_file(output / "source-snapshot.json", json_bytes(snapshot))
    print(json.dumps({"snapshot_id": snapshot["snapshot_id"], "head": snapshot["git_head"], "output": str(output)}), flush=True)
    checks = []
    try:
        checks.append(run(output, "ruff", [sys.executable, "-m", "ruff", "check", "."], snapshot))
        checks.append(run(output, "types", [sys.executable, "tools/check_types.py"], snapshot))
        with ThreadPoolExecutor(max_workers=2) as pool:
            backend = pool.submit(run, output, "full-backend", [sys.executable, "tools/verify_zhigou_upgrade.py",
                "--backend-only", "--workers", "4", "--skip-model-probe"], snapshot) if args.full_backend else None
            if backend is None:
                checks.append(run(output, "focused", [], snapshot, pytest_args=["tests/upgrade/test_scenario_configuration.py",
                    "tests/upgrade/test_scenario_requests.py", "tests/upgrade/test_scenario_quality.py", "tests/services/test_scenario_authority.py",
                    "tests/services/test_scenario_service.py", "tests/upgrade/test_expert_loop.py", "tests/services/test_expert_service.py",
                    "tests/services/test_expert_authority.py", "tests/upgrade/test_step_audit.py", "tests/upgrade/test_prompt_audit.py",
                    "tests/upgrade/test_evolution_delivery.py", "tests/upgrade/test_agent_roles.py"]))
            npm = "npm.cmd" if os.name == "nt" else "npm"
            for name in ("lint", "typecheck", "test", "build"):
                checks.append(run(output, "frontend-" + name, [npm, "--prefix", "workbench", "run", name], snapshot))
            if backend:
                checks.append(backend.result())
        # Do not compete with the four-worker validator load of the full run.
        checks.append(run(output, "three-scene-prompt-presets", [sys.executable, "-m", "tools.verify_scenario_workbench",
            str(output / "cases")], snapshot))
        checks.append(run(output, "browser", [sys.executable, "tools/run_browser_verification.py", "--selected-test", "scenario.e2e.ts", "--startup-timeout", "90"], snapshot))
        after = assert_unchanged(ROOT, snapshot)
        backend_report = None
        if args.full_backend:
            nested = next((Path(r["evidence"]) for r in json_records(output / "checks/full-backend/command.log") if "evidence" in r), None)
            if nested:
                backend_report = {"output": str(nested), **junit(nested / "backend.xml")}
        report = {"raw_status": "PASS" if all(c["exit_code"] == 0 for c in checks) else "FAIL", "checks": checks,
            "backend": backend_report, "source_snapshot_id": snapshot["snapshot_id"], "source_after": after, "source_unchanged": True,
            "paid_calls": 0, "model_nature": "MOCK_TRANSPORT", "human_nature": "SYNTHETIC_TEST_IDENTITIES",
            "full_backend": "RUN" if args.full_backend else "NOT_RUN", "live_expert_trial": "NOT_RUN", "receiver": "NOT_CONTACTED", "release": "NOT_PERFORMED"}
        atomic_file(output / "verification.json", json_bytes(report))
        lines = ["# 场景 Prompt 预设：冻结原始验证", "", "HEAD: " + snapshot["git_head"], "", "源码快照: " + snapshot["snapshot_id"],
            "", "原始结论: " + report["raw_status"] + "；source_unchanged=true。", ""]
        lines += [f"- {c['name']}: exit_code={c['exit_code']}；checks/{c['name']}/command.log" for c in checks]
        lines += ["", "合成来源/专家身份，模型仅 MockTransport；没有付费、推送、发布、外部接收或真实业务动作。", ""]
        atomic_file(output / "FINAL_REPORT.md", "\n".join(lines).encode("utf-8"))
        print(json.dumps({"raw_status": report["raw_status"], "source_unchanged": True, "output": str(output)}), flush=True)
    except BaseException as exc:
        atomic_file(output / "ABORTED.json", json_bytes({"status": "ABORTED_NOT_QUALIFIED", "error_type": type(exc).__name__,
            "reason": str(exc), "checks_completed": checks, "source_snapshot_id": snapshot["snapshot_id"]}))
        raise


if __name__ == "__main__":
    main()
