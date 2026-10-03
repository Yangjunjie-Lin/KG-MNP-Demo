"""Finite authorized smoke -> pilot -> full -> offline scoring workflow.

Stops on failures, unknown budget, user stop or resource limits. No new policy,
credential discovery, new model, gold-driven repair or budget increase here.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from zhigou_toolchain.ontology_io.budget_monitor import ENDPOINT, MODEL
from zhigou_toolchain.ontology_io.cli import load, save
from zhigou_toolchain.ontology_io.live_exports import finalize
from zhigou_toolchain.ontology_io.live_runner import execute, status, supervisor_lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    revision = workspace / "revisions" / args.revision
    manifest = load(revision / "manifest.json")
    if not manifest.get("budget_monitor") or manifest["binding"]["model_id"] != MODEL:
        raise ValueError("EXPLICIT_LUNA_MONITORED_REVISION_REQUIRED")
    # Process-local configuration only. Existing secret remains in memory.
    os.environ.update(OPENAI_TEXT_MODEL=MODEL, OPENAI_BASE_URL=ENDPOINT, OPENAI_REASONING_EFFORT="low",
        ZHIGOU_LLM_REVISION="configured-alias:" + MODEL, KG_MNP_LLM_REVISION="configured-alias:" + MODEL)
    for phase in ("smoke", "pilot", "full"):
        with supervisor_lock(workspace):
            current = status(workspace, args.revision)
            rows = [r for r in current["jobs"] if r["phase"] == phase]
            if phase != "full" and any(r["state"] == "FAILED" for r in rows):
                save(revision / "workflow-status.json", {"status": "PAUSED_FAILED_PRECHECK", "phase": phase, "snapshot": current})
                return
            result = execute(workspace, args.revision, phase)
        save(revision / (phase + "-completion.json"), result)
        rows = [r for r in result["jobs"] if r["phase"] == phase]
        pending = any(r["state"] in {"PENDING", "RUNNING"} for r in rows)
        precheck_failed = phase != "full" and any(r["state"] == "FAILED" for r in rows)
        if pending or precheck_failed:
            save(revision / "workflow-status.json", {"status": "PAUSED_INCOMPLETE_OR_FAILED", "phase": phase, "snapshot": result})
            print(json.dumps({"status": "PAUSED_INCOMPLETE_OR_FAILED", "phase": phase}), flush=True)
            return
        print(json.dumps({"status": "PHASE_TERMINAL", "phase": phase}), flush=True)
    destination = revision / "full-scoring"
    with supervisor_lock(workspace):
        result = finalize(workspace, args.revision, destination)
    report = load(destination / "report.json")
    complete = report.get("primary_comparison_family_complete", False) and all(r["status"].get("status") == "MEASURED" for r in report["summaries"])
    save(revision / "workflow-status.json", {"status": "SCORED" if complete else "GENERATION_TERMINAL_SCORING_INCOMPLETE",
        "scoring": result, "scores": str(destination), "all_requested_quality_results_complete": complete})
    print(json.dumps({"status": "SCORED" if complete else "SCORING_INCOMPLETE", "scores": str(destination)}), flush=True)


if __name__ == "__main__":
    main()
