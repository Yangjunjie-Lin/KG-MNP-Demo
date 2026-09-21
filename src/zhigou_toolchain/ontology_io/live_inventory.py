"""Gold-free offline inventory, not a partial-success quality evaluation."""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash

from .adapters import project_task_prediction
from .cli import save
from .contracts import ModelingInput
from .live_budget import BudgetLedger
from .live_runner import supervisor_lock


def snapshot(workspace, revision, output):
    """Verify retained artifacts and include every pending/failed/N/A slot.

    No model configuration, generation, scoring gold or success-only metrics.
    Historical evidence is never overwritten. Databases are read, not changed.
    """
    workspace, output = Path(workspace).resolve(strict=True), Path(output).resolve()
    if not revision.isalnum() or len(revision) > 30:
        raise ValueError("INVALID_REVISION_NAME")
    rev, evidence = workspace / "revisions" / revision, {}

    def read_locked(path):
        path = Path(path)
        if not path.resolve(strict=True).is_relative_to(workspace) or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("SNAPSHOT_EVIDENCE_PATH_INVALID")
        raw = path.read_bytes()
        evidence[path.relative_to(workspace).as_posix()] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    def read_db(name, sql, parameters=()):
        with closing(sqlite3.connect((workspace / name).as_uri() + "?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, parameters)]

    with supervisor_lock(workspace):
        jobs = read_db("jobs.sqlite", "SELECT * FROM jobs WHERE revision=? ORDER BY phase,task,system,sample,replicate", (revision,))
        if not jobs or any(r["state"] == "RUNNING" for r in jobs):
            raise ValueError("SNAPSHOT_REQUIRES_KNOWN_QUIESCENT_REVISION")
        if any(r["state"] not in {"PENDING", "GENERATED", "FAILED", "NOT_APPLICABLE"} for r in jobs):
            raise ValueError("SNAPSHOT_UNKNOWN_JOB_STATE")
        for name in ("jobs.sqlite", "budget.sqlite"):
            evidence[name] = hashlib.sha256((workspace / name).read_bytes()).hexdigest()
        public = {(r["phase"], r["task"], r["sample"]): json.loads(r["payload"])
            for r in read_db("jobs.sqlite", "SELECT * FROM inputs WHERE revision=?", (revision,))}
        budget = BudgetLedger(workspace / "budget.sqlite").snapshot()
        attempts = read_db("budget.sqlite", "SELECT * FROM attempts ORDER BY request_id")
        manifest = read_locked(rev / "manifest.json")
        protocols = {key: read_locked(rev / "protocols" / (key + ".json")) for key in {r["task"] for r in jobs}}
        by_job = defaultdict(list)
        for attempt in attempts:
            by_job[attempt["job_id"]].append(attempt)
        summaries, inventory, verified = {}, [], 0
        for row in jobs:
            item = public[(row["phase"], row["task"], row["sample"])]
            protocol, calls, result_ref = protocols[row["task"]], by_job[row["job_id"]], None
            if row["result_path"]:
                result_path = Path(row["result_path"])
                if not result_path.resolve().is_relative_to((rev / "runs" / row["job_id"]).resolve()):
                    raise ValueError("SNAPSHOT_RESULT_JOB_PATH_MISMATCH")
                result = read_locked(result_path)
                if semantic_hash(result) != row["result_hash"]:
                    raise ValueError("FROZEN_PREDICTION_CHANGED")
                expected = {"sample_id": row["sample"], "group_id": item["group_id"], "system_id": row["system"],
                    "replicate_id": row["replicate"], "status": row["state"], "input_sha256": semantic_hash(item)}
                if any(result.get(k) != v for k, v in expected.items()):
                    raise ValueError("SNAPSHOT_RESULT_CONTEXT_CHANGED")
                result_ref = result_path.relative_to(workspace).as_posix()
                if row["state"] == "GENERATED":
                    artifacts = result_path.parent / "artifacts"
                    if read_locked(artifacts / "projection.json") != result["prediction"]:
                        raise ValueError("FROZEN_PROJECTION_CHANGED")
                    for member in artifacts.rglob("*"):
                        if member.is_symlink() or not member.resolve().is_relative_to(artifacts.resolve()):
                            raise ValueError("SNAPSHOT_ARTIFACT_LINK_REJECTED")
                        if member.is_file():
                            evidence[member.relative_to(workspace).as_posix()] = hashlib.sha256(member.read_bytes()).hexdigest()
                    project_task_prediction(artifacts, ModelingInput.model_validate(item))
                    verified += 1
            elif row["state"] == "GENERATED":
                raise ValueError("GENERATED_WITHOUT_FROZEN_PREDICTION")
            durations = []
            for call in calls:
                number = call["request_id"].rsplit(":call-", 1)[-1]
                if not number.isdigit():
                    raise ValueError("UNKNOWN_JOB_CALL_ID")
                response = read_locked(rev / "runs" / row["job_id"] / "calls" / number / "response.json")
                if semantic_hash(response) != call["result_hash"]:
                    raise ValueError("FROZEN_CALL_RESPONSE_CHANGED")
                metadata = response.get("receipt") or response.get("public_response") or {}
                durations.append(metadata.get("duration_seconds"))
            key = (row["phase"], row["task"], row["system"])
            if key not in summaries:
                summaries[key] = {"benchmark": item["benchmark_id"], "task": item["task_id"], "routing_task": row["task"],
                    "scope": "ENGINEERING_CHECK" if row["phase"] == "smoke" else "PILOT" if row["phase"] == "pilot" else item["evaluation_scope"],
                    "phase": row["phase"], "system": row["system"], "model": manifest["binding"]["model_id"],
                    "declared_revision": manifest["binding"]["declared_revision"],
                    "profile": (protocol.get("kernel_profile") or {}).get("profile_id") if row["system"] not in {"DirectGeneralLLM", "DirectBudgetControl"} else row["system"],
                    "samples": set(), "groups": set(), "states": Counter(), "calls": 0, "known_tokens": [], "model_seconds": [],
                    "primary_metrics": protocol["primary_metrics"], "matching": protocol["matching"]}
            summary = summaries[key]
            summary["samples"].add(row["sample"])
            summary["groups"].add(item["group_id"])
            summary["states"][row["state"]] += 1
            summary["calls"] += len(calls)
            summary["known_tokens"].extend(c["usage"] for c in calls)
            summary["model_seconds"].extend(durations)
            inventory.append({k: row[k] for k in ("job_id", "phase", "task", "sample", "system", "replicate", "state", "error")} | {
                "group_id": item["group_id"], "input_sha256": semantic_hash(item), "result_ref": result_ref,
                "result_sha256": row["result_hash"], "calls": len(calls), "known_tokens": sum(c["usage"] for c in calls)
                if calls and all(c["usage"] is not None for c in calls) else None})
        rows = []
        for summary in summaries.values():
            states = summary.pop("states")
            sample_count, group_count = len(summary.pop("samples")), len(summary.pop("groups"))
            known, durations = summary.pop("known_tokens"), summary.pop("model_seconds")
            planned = sum(states.values()) - states["NOT_APPLICABLE"]
            primary = summary.pop("primary_metrics")
            common = {**summary, "sample_count": sample_count, "group_count": group_count, "planned_runs": planned,
                "success": states["GENERATED"], "failed": states["FAILED"], "not_run": states["PENDING"], "not_applicable": states["NOT_APPLICABLE"],
                "completion": (states["GENERATED"] + states["FAILED"]) / planned if planned else None,
                "tokens": sum(known) if known and all(v is not None for v in known) else None,
                "model_seconds": sum(durations) if durations and all(v is not None for v in durations) else None,
                "cost": None, "score": None, "paired_delta": None, "ci_lower": None, "ci_upper": None,
                "status": "NOT_APPLICABLE" if not planned else "ENGINEERING_CHECK" if summary["phase"] == "smoke" else "BLOCKED",
                "metric_status": "NOT_SCORED_IN_STATUS_SNAPSHOT"}
            rows.extend({**common, "metric": name} for name in primary)
        job_ids = {r["job_id"] for r in jobs}
        counts = Counter((r["phase"], r["state"]) for r in jobs)
        report = {"status": "OFFLINE_STATUS_SNAPSHOT", "revision": revision, "model_calls_by_this_command": 0,
            "gold_files_opened": 0, "experiment_complete": False, "research_score": None, "budget": budget,
            "verified_generated_artifacts": verified, "all_job_slots": len(jobs),
            "counts": [{"phase": p, "state": s, "count": n} for (p, s), n in sorted(counts.items())],
            "calls_outside_revision_jobs": sum(a["job_id"] not in job_ids for a in attempts),
            "frozen_source_commit": manifest["source_identity"]["commit"],
            "frozen_source_sha256": manifest["source_identity"]["fingerprint"]["digest"],
            "limitations": ["Status snapshot only; not a final evaluation or official score",
                "Smoke inputs are synthetic; routing profile names are not evidence for those benchmarks",
                "All pending/failed slots retained; N/A and seed repeats are not completed independent samples",
                "Missing token/time/cost values are null; completion means terminal jobs, not prediction success",
                "OSKGC licence, full CQ4OE and semantic scoring remain separately blocked",
                "No expert comparison; task-adapted kernel is not the complete production Ours"], "results": rows}
        comparison = {"status": "BLOCKED", "improvement_supported": None, "comparisons": [
            {"task": task, "baseline": baseline, "experiment": "TwoAgentKernelV1", "delta": None, "ci95": None,
                "status": "BLOCKED", "reason": "FULL_PREDICTIONS_NOT_COMPLETE_OR_NOT_SCORED"}
            for task in sorted({r["task"] for r in rows if r["phase"] == "full"}) for baseline in ("DirectGeneralLLM", "DirectBudgetControl")],
            "not_a_claim": "Inventory only: no research metrics or hypothesis tests were computed."}
        output.mkdir(parents=True, exist_ok=False)
        save(output / "report.json", report)
        save(output / "comparison.json", comparison)
        save(output / "evidence-lock.json", dict(sorted(evidence.items())))
        with (output / "jobs.jsonl").open("w", encoding="utf-8") as stream:
            for item in inventory:
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
        with (output / "results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows({k: "null" if v is None else v for k, v in r.items()} for r in rows)
        text = ["# Offline experiment status (not quality results)", "", f"Revision: {revision}. Full evaluation is not complete.", "",
            f"Actual calls: {budget['calls']}; known tokens: {budget['known_tokens']}; cost: unknown.",
            f"Verified generated artifacts: {verified}; inventoried job slots: {len(jobs)}.", "",
            "No score, paired delta, confidence interval or improvement claim is available.", "",
            "| Phase | State | Runs |", "| --- | --- | ---: |"]
        text.extend(f"| {p} | {s} | {n} |" for (p, s), n in sorted(counts.items()))
        text.extend(["", "Original sample/system/repeat IDs remain in jobs.jsonl. results.csv contains explicit null scores.", "",
            "Reproduce without model credentials or network:", "", "```powershell",
            f'python tools/finalize_ontology_experiment.py --mode snapshot --workspace "{workspace}" --revision {revision} --output "{output}-replay"',
            "```", "", *["- " + limitation for limitation in report["limitations"]]])
        (output / "report.md").write_text("\n".join(text) + "\n", encoding="utf-8")
        save(output / "sha256.json", {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())})
    return {"status": report["status"], "model_calls": 0, "job_slots": len(jobs), "verified_generated_artifacts": verified,
        "research_score": None, "output": str(output)}
