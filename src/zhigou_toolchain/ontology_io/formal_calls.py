"""Prepare complete, bounded call plans. Never spend or grant authorization.

Caps derive from the ACTUAL task-adapted kernel: a text run has a vocabulary
call, extraction call, optional reuse call, then at most two calls per repair;
CQs-only has one design call and at most one call per repair. No gold is read.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash

from .cli import ROOT, load, save
from .contracts import ModelingInput, Protocol
from .cq4oe import CQ4OE_COMMIT
from .kernel import components, task_cards
from .native_metrics import LLMS4OL_COMMIT
from .provenance import source_identity

CORE = ["DirectGeneralLLM", "DirectBudgetControl", "TwoAgentKernelV1"]
ALL_SYSTEMS = [*CORE, "NoRetrieval", "NoConstrainedExtraction", "NoValidationFeedback", "DirectRetrievalContext"]
TASKS = {
    "llms4ol_2026--flagship": (4, ["graph_similarity"]),
    "llms4ol_2026--reuse": (5, ["edge_f1"]),
    "cq4oe_0_0_1--cq2term": (2, ["classes_f1", "properties_f1"]),
    "cq4oe_0_0_1--cq2onto": (2, ["Axiom"]),
}


def call_cap(sample, protocol, system):
    if system == "DirectGeneralLLM":
        return 1
    if system == "DirectBudgetControl":
        return protocol.budget.max_calls
    active = components(sample, protocol, system)
    if system == "DirectRetrievalContext":
        return 1
    is_text = sample.mode != "CQS_TBOX"
    base = (2 if is_text else 1) + int(bool(task_cards(sample)))
    repairs = protocol.kernel_profile.max_repair_cycles if active["enabled"]["validation_feedback"] else 0
    return min(protocol.budget.max_calls, base + repairs * (2 if is_text else 1))


def task_protocol(key, *, model_id, declared_revision, reasoning_effort):
    cap, primary = TASKS[key]
    return Protocol.model_validate({"protocol_id": "formal-request-candidate-v1--" + key, "model_id": model_id, "declared_revision": declared_revision,
        "reasoning_effort": reasoning_effort, "systems": ALL_SYSTEMS, "replicates": 3, "matching": "exact", "primary_metrics": primary,
        "budget": {"max_calls": cap, "max_output_tokens": 8192, "max_input_characters": 24000,
            "context_window_tokens": 32768, "max_total_tokens": cap * 32768},
        "request_profile": {"completion_token_parameter": "max_completion_tokens", "response_format": "json_object",
            "timeout_seconds": 120, "n": 1, "stream": False, "store": False},
        "kernel_profile": {"reasoner_jar": "third_party/downloads/robot-1.9.7.jar", "max_repair_cycles": 1},
        "bootstrap_samples": 2000, "statistics_seed": 1729})


def prepare_call_pack(prepared_root, output, *, observed_configuration):
    root, output = Path(prepared_root), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    identity = source_identity(ROOT)
    jobs, source_locks, summaries = [], {}, []
    models = {k: observed_configuration[k] for k in ("model_id", "declared_revision", "reasoning_effort")}
    for key in TASKS:
        prepared = root / key
        raw = load(prepared / "generation/inputs.json")
        lock = load(prepared / "prepared-lock.json")
        if semantic_hash(raw) != lock["input_sha256"]:
            raise ValueError("FORMAL_SOURCE_INPUT_CHANGED")
        samples = [ModelingInput.model_validate(row) for row in raw]
        expected_version = LLMS4OL_COMMIT if key.startswith("llms4ol") else CQ4OE_COMMIT
        if lock["dataset_version"] != expected_version or any(s.dataset_version != expected_version
                or s.benchmark_id + "--" + s.task_id != key for s in samples):
            raise ValueError("FORMAL_TASK_OR_DATASET_CONTEXT_CHANGED")
        if len({s.sample_id for s in samples}) != len(samples) or len(samples) != lock["sample_count"]:
            raise ValueError("FORMAL_INPUT_INVENTORY_INVALID")
        protocol = task_protocol(key, **models)
        normalized = [s.model_dump(mode="json") for s in samples]
        input_sha = semantic_hash(normalized)
        source_locks[key] = {"source_input_sha256": lock["input_sha256"], "effective_input_sha256": input_sha,
            "prepared_lock_sha256": semantic_hash(lock), "dataset_version": lock["dataset_version"]}
        save(output / "generation" / key / "inputs.json", normalized)
        save(output / "protocols" / (key + ".json"), protocol.model_dump(mode="json"))
        counts, caps = Counter(), Counter()
        for sample in samples:
            for system in ALL_SYSTEMS:
                try:
                    cap = call_cap(sample, protocol, system)
                    eligible = True
                except ValueError as exc:
                    if str(exc) != "ABLATION_COMPONENT_NOT_ACTIVE_IN_PARENT_PROFILE":
                        raise
                    cap, eligible = 0, False
                counts[system] += int(eligible)
                caps[system] += cap * protocol.replicates
                for rep in range(protocol.replicates):
                    jobs.append({"task": key, "sample_id": sample.sample_id, "group_id": sample.group_id,
                        "system": system, "replicate_id": rep, "eligible": eligible, "max_calls": cap,
                        "max_reserved_tokens": cap * protocol.budget.context_window_tokens,
                        "status": "PENDING_AUTHORIZATION_AND_QUALIFICATION" if eligible else "NOT_APPLICABLE_COMPONENT_ABSENT"})
        for system in ALL_SYSTEMS:
            summaries.append({"task": key, "system": system, "source_samples": len(samples), "eligible_samples": counts[system],
                "not_applicable_samples": len(samples) - counts[system], "replicates": protocol.replicates,
                "call_cap": caps[system], "reserved_token_cap": caps[system] * protocol.budget.context_window_tokens,
                "score": None, "status": "NOT_RUN" if counts[system] else "NOT_APPLICABLE"})
    with (output / "jobs.jsonl").open("x", encoding="utf-8") as stream:
        for row in jobs:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output / "budget.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows({k: "null" if v is None else v for k, v in row.items()} for row in summaries)
    totals = defaultdict(int)
    for row in jobs:
        totals["all_calls"] += row["max_calls"]
        totals["all_reserved_tokens"] += row["max_reserved_tokens"]
        totals["eligible_run_units"] += int(row["eligible"])
        totals["na_run_units"] += int(not row["eligible"])
        if row["system"] in CORE:
            totals["core_calls"] += row["max_calls"]
            totals["core_reserved_tokens"] += row["max_reserved_tokens"]
    readiness = {"status": "FORMAL_CALL_PACK_PREPARED_NOT_AUTHORIZED_NOT_EXECUTED", "source_identity": identity,
        "source_unchanged": source_identity(ROOT) == identity, "observed_configuration": observed_configuration,
        "source_inputs": source_locks, "totals": dict(totals), "per_system": summaries,
        "jobs_sha256": semantic_hash(jobs), "generation_calls": 0, "research_scores": None,
        "proposal_not_authorization": {"core_max_calls": totals["core_calls"], "core_max_reserved_tokens": totals["core_reserved_tokens"],
            "all_max_calls": totals["all_calls"], "all_max_reserved_tokens": totals["all_reserved_tokens"], "user_approval": None},
        "blockers": ["TOTAL_BUDGET_NOT_AUTHORIZED", "GATEWAY_POST_PARAMETERS_NOT_VERIFIED", "OS_GENERATION_ISOLATION_NOT_READY",
            "HISTORICAL_HOLDOUT_CONTACT_AUDIT_PENDING", "CQ4OE_COMPLETE_NATIVE_SCORER_PENDING"],
        "excluded_but_not_forgotten": {"OSKGC": "BLOCKED_DATA_LICENSE_CONFLICT_FULL_SAMPLE_COUNT_UNKNOWN",
            "Ontogenia": "BLOCKED_REQUIRED_METHOD_ASSETS_AND_TASK_ADAPTATION", "MemorylessCQbyCQ": "PAPER_TASK_ADAPTATION_NOT_FROZEN",
            "semantic_matching": "BLOCKED_SCORING_MODEL_CODE_AND_WEIGHT_LOCK"}}
    save(output / "call-pack.json", readiness)
    save(output / "source-after.json", source_identity(ROOT))
    return {"status": readiness["status"], "totals": dict(totals), "source_unchanged": readiness["source_unchanged"], "output": str(output)}
