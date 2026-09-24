"""Export frozen full predictions to the existing independent scorer.

No prediction is repaired here. Failed jobs remain in every expected inventory.
This module never calls a model and refuses partially running full experiments.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash

from .cli import ROOT, compare, load, save, score
from .contracts import ModelingInput, Protocol
from .live_budget import BudgetLedger
from .live_inventory import call_response_path
from .live_runner import connect
from .quality_exports import write_quality_tables


def verify_full_inventory(jobs, inputs, protocols, locks):
    if not jobs or not inputs:
        raise ValueError("EMPTY_FULL_EXPERIMENT_NOT_COMPLETE")
    actual = [(r["task"], r["sample"], r["system"], r["replicate"]) for r in jobs]
    expected = {(task, sid, system, rep) for task, sid in inputs
        for system in protocols[task].systems for rep in range(protocols[task].replicates)}
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("FULL_JOB_INVENTORY_MISSING_DUPLICATED_OR_CHANGED")
    for task, entry in locks.items():
        original = load(Path(entry["legacy_prepared"]) / "generation/inputs.json")
        if semantic_hash(original) != entry["lock"]["input_sha256"]:
            raise ValueError("FULL_PUBLIC_SOURCE_CHANGED")
        normalized = [ModelingInput.model_validate(r).model_dump(mode="json") for r in original]
        if semantic_hash(normalized) != entry["effective_input_sha256"]:
            raise ValueError("FROZEN_FULL_NORMALIZED_INPUT_CHANGED")
        present = {sid: value for (key, sid), value in inputs.items() if key == task}
        if present != {r["sample_id"]: r for r in normalized}:
            raise ValueError("FULL_INPUT_INVENTORY_CHANGED")


def finalize(workspace, revision, output):
    workspace, output = Path(workspace).resolve(), Path(output).resolve()
    rev = workspace / "revisions" / revision
    with connect(workspace) as conn:
        pending = conn.execute("SELECT COUNT(*) FROM jobs WHERE revision=? AND phase='full' AND state IN ('PENDING','RUNNING')", (revision,)).fetchone()[0]
        if pending:
            raise ValueError("FULL_PREDICTIONS_NOT_FROZEN")
        planned = [dict(r) for r in conn.execute("SELECT * FROM jobs WHERE revision=? AND phase='full' ORDER BY task,system,sample,replicate", (revision,))]
        inputs = {(r["task"], r["sample"]): json.loads(r["payload"]) for r in conn.execute("SELECT * FROM inputs WHERE revision=? AND phase='full'", (revision,))}
        histories = {}
        if conn.execute("SELECT name FROM sqlite_master WHERE name='execution_attempts'").fetchone():
            for row in conn.execute("SELECT e.* FROM execution_attempts e JOIN jobs j ON e.job_id=j.job_id WHERE j.revision=? AND j.phase='full' ORDER BY e.job_id,e.attempt", (revision,)):
                histories.setdefault(row["job_id"], []).append(json.loads(row["snapshot"]))
    manifest = load(rev / "manifest.json")
    locks = load(rev / "input-locks.json")
    protocols = {task: Protocol.model_validate(load(rev / "protocols" / (task + ".json"))) for task in locks}
    verify_full_inventory(planned, inputs, protocols, locks)
    jobs = [r for r in planned if r["state"] != "NOT_APPLICABLE"]
    job_ids = {r["job_id"] for r in jobs}
    call_accounting = {}
    with BudgetLedger(workspace / "budget.sqlite").connection() as conn:
        for row in conn.execute("SELECT request_id,job_id,state,usage,reserved_at_dispatch,result_hash FROM attempts ORDER BY request_id"):
            if row["job_id"] in job_ids:
                response_path = call_response_path(rev, row["job_id"], row["request_id"])
                if response_path.is_symlink() or not response_path.resolve().is_relative_to(rev.resolve()) or semantic_hash(load(response_path)) != row["result_hash"]:
                    raise ValueError("FROZEN_ATTEMPT_RESPONSE_CHANGED")
                call_accounting.setdefault(row["job_id"], []).append(dict(row))
    output.mkdir(parents=True, exist_ok=False)
    summaries, reports = [], {}
    for task, system in sorted({(r["task"], r["system"]) for r in jobs}):
        subset = [r for r in jobs if (r["task"], r["system"]) == (task, system)]
        ids = sorted({r["sample"] for r in subset})
        public = [inputs[(task, sid)] for sid in ids]
        protocol = Protocol.model_validate(load(rev / "protocols" / (task + ".json")))
        if protocol.kernel_profile is not None:
            protocol = protocol.model_copy(update={"kernel_profile": protocol.kernel_profile.model_copy(update={"reasoner_jar": "/opt/robot.jar"})})
        run = output / task / system / "run"
        run.mkdir(parents=True)
        save(run / "generation-inputs.json", public)
        records, accounting = [], {}
        for row in subset:
            name = f"{row['sample']}-{row['replicate']}"
            if row["result_path"]:
                source = Path(row["result_path"])
                if source.is_symlink() or not source.resolve().is_relative_to(rev.resolve()):
                    raise ValueError("FROZEN_RESULT_PATH_INVALID")
                result = load(source)
                if semantic_hash(result) != row["result_hash"]:
                    raise ValueError("FROZEN_RESULT_CONTENT_CHANGED")
                for member in source.parent.rglob("*"):
                    if member.is_symlink() or not member.resolve().is_relative_to(source.parent.resolve()):
                        raise ValueError("FROZEN_OUTPUT_SYMLINK_OR_ESCAPE")
                shutil.copytree(source.parent, run / name, symlinks=False)
            else:
                item = inputs[(task, row["sample"])]
                result = {"sample_id": row["sample"], "group_id": item["group_id"], "replicate_id": row["replicate"],
                    "system_id": system, "status": "FAILED", "failure_type": row["error"], "failure_code": "INFRASTRUCTURE_NO_PREDICTION",
                    "protocol_sha256": semantic_hash(protocol.model_dump(mode="json")), "input_sha256": semantic_hash(item),
                    "calls": [], "resources": {"model_calls": None, "reported_total_tokens": None, "cost": None}, "prediction": None}
                save(run / name / "result.json", result)
            records.append({"sample_id": row["sample"], "group_id": result["group_id"], "replicate_id": row["replicate"], "path": name,
                "status": result["status"], "result_sha256": semantic_hash(result)})
            calls = call_accounting.get(row["job_id"], [])
            accounting[name] = {"model_calls_all_attempts": len(calls), "reported_total_tokens_all_attempts": sum(c["usage"] for c in calls)
                if calls and all(c["usage"] is not None for c in calls) else None,
                "known_reported_tokens_all_attempts": sum(c["usage"] for c in calls if c["usage"] is not None),
                "unknown_usage_calls": sum(c["usage"] is None for c in calls), "execution_attempt_count": len(histories.get(row["job_id"], [])) or 1}
            save(run / name / "execution-attempt-history.json", {"attempts": histories.get(row["job_id"], []), "calls": calls,
                "scope": "ALL_RETAINED_ATTEMPTS_NOT_JUST_FINAL_SUCCESS"})
        generation = {"run_id": revision + ":" + task + ":" + system, "system_id": system,
            "status": "FROZEN_PREDICTIONS", "protocol": protocol.model_dump(mode="json"), "protocol_sha256": semantic_hash(protocol.model_dump(mode="json")),
            "input_sha256": semantic_hash(public), "samples": records, "source_commit": manifest["source_identity"]["commit"],
            "source_fingerprint_sha256": manifest["source_identity"]["fingerprint"]["digest"], "generation_runtime": manifest["isolation"]["runtime"],
            "isolation": manifest["isolation"], "source_unchanged": True, "execution_accounting": accounting}
        save(run / "run.json", generation)
        prepared = output / task / system / "scoring-prepared"
        old = locks[task]["lock"]
        old_gold_path = Path(locks[task]["legacy_prepared"]) / "scoring/gold.json"
        if old_gold_path.exists():
            target = load(old_gold_path)
            if semantic_hash(target) != old["gold_sha256"]:
                raise ValueError("FROZEN_GOLD_CHANGED")
            selected = {sid: target[sid] for sid in ids}
            save(prepared / "scoring/gold.json", selected)
            save(prepared / "prepared-lock.json", {**old, "input_sha256": semantic_hash(public), "gold_sha256": semantic_hash(selected), "sample_count": len(ids)})
        report_path = output / task / system / "score.json"
        try:
            upstream = ROOT / "runtime/ontology-io/upstream" / old["benchmark_id"] / old["dataset_version"]
            status = score(run, prepared, upstream, report_path)
            reports[(task, system)] = report_path
            metrics = load(report_path)["metrics"]
        except (ValueError, FileNotFoundError) as exc:
            status = {"status": "BLOCKED_NATIVE_SCORER", "error_type": type(exc).__name__}
            metrics = []
        summaries.append({"task": task, "system": system, "sample_count": len(ids), "runs": len(subset),
            "completed": sum(r["state"] == "GENERATED" for r in subset), "failed": sum(r["state"] != "GENERATED" for r in subset),
            "status": status, "metrics": metrics, "primary_metrics": protocol.primary_metrics})
    comparisons, paired_reports = [], {}
    for task in sorted({r["task"] for r in summaries}):
        for baseline in ("DirectGeneralLLM", "DirectBudgetControl"):
            a, b = reports.get((task, baseline)), reports.get((task, "TwoAgentKernelV1"))
            if a and b:
                try:
                    destination = output / task / (baseline + "-paired.json")
                    paired_reports[(task, baseline)] = compare(a, b, destination)
                    comparisons.append({"task": task, "baseline": baseline, "report": str(destination)})
                except ValueError as exc:
                    comparisons.append({"task": task, "baseline": baseline, "status": "INCONCLUSIVE", "reason": str(exc)})
    quality = write_quality_tables(output, summaries, paired_reports)
    report = {"status": "SCORING_ATTEMPTED", "summaries": summaries, "comparisons": comparisons,
        "quality_and_effects": "quality-and-effects.json", "primary_comparison_family_complete": quality["primary_family_complete"],
        "limitations": ["Primary report remains UNSCORABLE if any required prediction failed; no success-only denominator",
            "Full CQ4OE and semantic matching remain separately gated; no fabricated substitute scores",
            "TwoAgentKernelV1 is the task-adapted profile, not full production Ours"], "model_calls": 0}
    save(output / "report.json", report)
    with (output / "results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["task", "system", "sample_count", "runs", "completed", "failed", "status"])
        writer.writeheader()
        writer.writerows({k: r[k] for k in writer.fieldnames} for r in summaries)
    save(output / "report-sha256.json", {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
        for name in ("report.json", "quality-and-effects.json", "quality-scores.csv", "effects.csv", "QUALITY_REPORT.md", "results.csv")})
    return {"status": "SCORING_ATTEMPTED", "task_systems": len(summaries), "model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=["finalize", "snapshot"], default="finalize",
        help="snapshot inventories every pending/failed slot offline without computing success-subset metrics")
    args = parser.parse_args()
    if args.mode == "snapshot":
        from .live_inventory import snapshot
        result = snapshot(args.workspace, args.revision, args.output)
    else:
        result = finalize(args.workspace, args.revision, args.output)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
