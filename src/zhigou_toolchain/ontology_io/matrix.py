"""Thin matrix audit/freeze/report entry point over the existing I/O CLI.

Never starts inference with an unset total budget, incomplete Ours or unverified
OS isolation. This module produces an honest NOT_RUN ledger, not predictions.
Existing frozen runs can be scored independently via the same score command.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from uuid import uuid4

import yaml

from zhigou_toolchain.contracts.canonical import semantic_hash

from .cli import ROOT, load, prepare, save, score, verify_assets
from .contracts import ModelingInput, Protocol
from .isolation import probe_isolation
from .provenance import runtime_versions, source_identity


def budget_upper_bound(sample_counts, systems, protocol):
    if any(not isinstance(n, int) or n < 0 for n in sample_counts):
        raise ValueError("INVALID_SAMPLE_COUNTS")
    n = sum(sample_counts) * protocol.replicates
    # Cap is reserved for every attempt, including failed requests. There is
    # no automatic retry. OursFull has a planned cap, not measured behaviour.
    calls = {s: n * (1 if s == "DirectGeneralLLM" else protocol.budget.max_calls) for s in systems}
    return {"planned_sample_system_replicates": n * len(systems), "model_call_upper_bound": sum(calls.values()),
        "calls_by_system": calls, "token_reservation_upper_bound": n * len(systems) * protocol.budget.max_total_tokens,
        "unplanned_retry_allowance": 0, "cost_upper_bound": None,
        "qualification": "ONLY_ENUMERATED_AVAILABLE_INPUTS_NOT_UNAVAILABLE_OSKGC_OR_PAPER_COMPONENTS"}


def validate_resume(frozen, current):
    for key in ("protocol_sha256", "source_fingerprint_sha256", "resource_locks", "input_locks", "phase"):
        if frozen[key] != current[key]:
            raise ValueError("RESUME_FROZEN_CONTEXT_CHANGED:" + key)


def execute(protocol_path, workspace, *, phase, resume=False):
    config = yaml.safe_load(Path(protocol_path).read_text(encoding="utf-8"))
    protocol = Protocol.model_validate(config["generation"])
    registry = yaml.safe_load((ROOT / config["source_registry"]).read_text(encoding="utf-8"))
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    phase_dir = workspace / phase
    existing = (phase_dir / "freeze.json").exists()
    if existing and not resume:
        raise ValueError("WORKSPACE_PHASE_EXISTS_USE_RESUME_OR_NEW_DIRECTORY")
    phase_dir.mkdir(parents=True, exist_ok=True)
    identity = source_identity(ROOT)
    resource_locks, inputs, coverage, paths = {}, {}, [], {}
    for task in config["tasks"]:
        benchmark, name = task["benchmark"], task["task"]
        key = benchmark + "--" + name
        upstream = ROOT / "runtime/ontology-io/upstream" / benchmark / registry["benchmarks"][benchmark]["commit"]
        verify_assets(upstream)
        resource_locks[benchmark] = hashlib.sha256((upstream / "asset-lock.json").read_bytes()).hexdigest()
        if benchmark == "cq4oe_0_0_1" and phase != "full":
            # All six ontologies reserved for evaluation; do not use the same
            # ontologies for public pilot development and full evaluation.
            coverage.append({"benchmark": benchmark, "task": name, "planned_samples": 0, "prepared_samples": 0,
                "planned_groups": 0, "scope": "PUBLIC_CQS_RESERVED_FOR_FULL_ONLY",
                "status": "NOT_APPLICABLE_USE_INDEPENDENT_SYNTHETIC_ENGINEERING_FIXTURES"})
            continue
        if benchmark == "oskgc":
            tree_path = upstream / "tree-lock.json"
            files = [r["path"] for r in load(tree_path)["tree"] if r["type"] == "blob" and r["path"].startswith("benchmark/data/test/")] if tree_path.exists() else []
            coverage.append({"benchmark": benchmark, "task": name, "planned_samples": None, "prepared_samples": 0, "planned_groups": None,
                "test_files_in_public_tree": files, "scope": "OFFICIAL_TEST_ALL_CATEGORIES_NOT_FETCHED", "status": "BLOCKED_LICENSE"})
            continue
        prepared = phase_dir / "prepared" / key
        if not prepared.exists():
            prepare(upstream, prepared, task=name, limit=None, phase=phase)
        lock = load(prepared / "prepared-lock.json")
        samples = load(prepared / "generation/inputs.json")
        if semantic_hash(samples) != lock["input_sha256"]:
            raise ValueError("PREPARED_INPUT_CHANGED")
        for sample in samples:
            ModelingInput.model_validate(sample)
        inputs[key] = semantic_hash(lock)
        paths[key] = (prepared, upstream, samples)
        coverage.append({"benchmark": benchmark, "task": name, "planned_samples": len(samples), "prepared_samples": len(samples),
            "planned_groups": len({s["group_id"] for s in samples}), "scope": lock.get("scope_label", "LOCAL_HOLDOUT"),
            "ontologies": lock.get("ontologies"), "status": "INPUTS_FROZEN_NOT_RUN"})
    frozen = {"matrix_id": config["matrix_id"], "protocol_sha256": semantic_hash(config), "source_fingerprint_sha256": identity["fingerprint"]["digest"],
        "phase": phase, "resource_locks": resource_locks, "input_locks": inputs, "source_identity": identity,
        "protocol": config, "runtime": runtime_versions()}
    if existing:
        validate_resume(load(phase_dir / "freeze.json"), frozen)
    else:
        save(phase_dir / "freeze.json", frozen)
    isolation = probe_isolation()
    blockers = ["BLOCKED_OS_ISOLATION", "BLOCKED_OURS_FULL_NOT_IMPLEMENTED", "BLOCKED_SAMPLING_PROTOCOL_NOT_FINAL",
        "BLOCKED_CQ4OE_FULL_NATIVE_PROFILE", "BLOCKED_OSKGC_LICENSE", "BLOCKED_HISTORICAL_DEVELOPMENT_OVERLAP_AUDIT"]
    if config["total_budget_authorization"] is None:
        blockers.insert(0, "BLOCKED_BUDGET_UNSET")
    attempt = phase_dir / "attempts" / uuid4().hex
    attempt.mkdir(parents=True)
    ledger = []
    for task in coverage:
        key = task["benchmark"] + "--" + task["task"]
        samples = paths.get(key, (None, None, []))[2]
        for sample in samples:
            for system in config["planned_systems"]:
                for repeat in range(protocol.replicates):
                    ledger.append({"benchmark": task["benchmark"], "task": task["task"], "sample_id": sample["sample_id"],
                        "group_id": sample["group_id"], "system": system, "replicate": repeat, "status": "NOT_RUN",
                        "reason": "BLOCKED_OURS_FULL_NOT_IMPLEMENTED" if system == "OursFull" else blockers[0],
                        "prediction": None, "calls": 0, "tokens": None, "time": None})
    save(attempt / "sample-ledger.json", ledger)
    summary = []
    for task in coverage:
        planned = task["planned_samples"]
        for system in config["planned_systems"]:
            summary.append({"benchmark": task["benchmark"], "task": task["task"], "scope": task["scope"], "system": system,
                "model": protocol.model_id, "profile": "NOT_IMPLEMENTED_FULL" if system == "OursFull" else "DIRECT_TASK_ADAPTER",
                "sample_count": planned, "group_count": task["planned_groups"],
                "metric": next(t["primary"] for t in config["tasks"] if t["task"] == task["task"]), "matching": "NATIVE_PLANNED",
                "score": None, "paired_delta": None, "ci95": None, "completion": 0, "calls": 0, "tokens": None, "time": None,
                "planned_runs": planned * protocol.replicates if planned is not None else None, "successful": 0, "failed": 0,
                "not_run": planned * protocol.replicates if planned is not None else None, "status": "BLOCKED"})
    save(attempt / "results.json", summary)
    with (attempt / "results.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows({k: "null" if v is None else v for k, v in row.items()} for row in summary)
    comparison = {"conclusion": "BLOCKED", "experiment_complete": False, "supports_improvement": None,
        "comparisons": [], "reason": "NO_FROZEN_EXTERNAL_MODEL_PREDICTIONS_NO_EFFECT_OR_CI", "blockers": blockers}
    save(attempt / "comparison.json", comparison)
    bound = budget_upper_bound([r["prepared_samples"] for r in coverage], config["planned_systems"], protocol)
    report = {"status": "BLOCKED", "phase": phase, "coverage": coverage, "budget": bound, "isolation": isolation,
        "blockers": blockers, "inference_calls": 0, "measured_native_metrics": None, "ledger_counts": dict(Counter(r["status"] for r in ledger)),
        "freeze_sha256": semantic_hash(load(phase_dir / "freeze.json")), "source_unchanged": source_identity(ROOT) == identity}
    report["paper_methods"] = [{"system": name, "benchmark": "onto_generation", "scope": "SAME_BACKBONE_RETEST_NOT_AUTHOR_ORIGINAL_SCORE",
        "planned_samples": None, "successful": 0, "failed": 0, "not_run": None, "status": "BLOCKED",
        "reason": "AUTHOR_PATTERNS_CSV_AND_PROCEDURE_ASSETS_NOT_PRESENT_IN_PINNED_TREE; TASK_STORY_ADAPTATION_NOT_FROZEN; NO_BUDGET",
        "human_judged_metrics": None, "calls": 0, "tokens": None} for name in config["paper_systems"]]
    report["metric_gaps"] = {"llms4ol": ["TASK_SUBTYPE_PR_OFFICIAL_AGGREGATION_NOT_IN_FIXED_SCORER", "SEMANTIC_MODEL_NOT_LOCKED"],
        "cq4oe": ["FULL_TOP3_ALIGNMENT", "PROPERTY_CHARACTERISTICS", "TBOX_TRIPLE", "AXIOM", "HIERARCHY_CLOSURE", "CQ_COVERAGE"],
        "oskgc": ["NO_AUTHORIZED_FULL_TEST_GENERATION", "NATIVE_AGGREGATE_COMPARE_CLI_NOT_CONNECTED"],
        "ours": ["SHARED_REUSE_STRUCTURE_KERNEL", "CONSTRAINED_EXTRACTION", "JOINT_VALIDATION_FEEDBACK", "BEHAVIOUR_PROVEN_ABLATIONS"]}
    save(attempt / "receipt.json", report)
    (attempt / "report.md").write_text("# External ontology comparison\n\nStatus: BLOCKED. No model predictions or comparative scores.\n\n"
        + "\n".join("- " + b for b in blockers) + "\n\nPlanned budget (available inputs only):\n\n```json\n" + json.dumps(bound, indent=2) + "\n```\n", encoding="utf-8")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in attempt.iterdir() if p.is_file()}
    save(attempt / "sha256.json", hashes)
    return {"status": "BLOCKED", "receipt": str(attempt / "receipt.json"), "budget": bound}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--phase", choices=["smoke", "pilot", "full", "score"], required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--upstream", type=Path)
    args = parser.parse_args(argv)
    if args.phase == "score":
        if not all((args.run, args.prepared, args.upstream)):
            parser.error("score requires --run --prepared --upstream (no model credentials)")
        output = args.workspace / ("score-" + uuid4().hex + ".json")
        result = score(args.run, args.prepared, args.upstream, output)
    else:
        result = execute(args.protocol, args.workspace, phase=args.phase, resume=args.resume)
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
