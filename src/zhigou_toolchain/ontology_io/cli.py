"""Independent research CLI. Scoring never calls generation or changes predictions."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path, PurePosixPath
from statistics import mean
from uuid import uuid4

import yaml
from jsonschema import Draft202012Validator

from zhigou_toolchain.contracts.canonical import semantic_hash

from .adapters import adapt_llms4ol, additions_only, project_task_prediction
from .contracts import REPORT_SCHEMA, ModelingInput, Protocol
from .engine import generate_sample
from .native_metrics import (
    LLMS4OL_COMMIT,
    LLMS4OL_SCORER_SHA256,
    llms4ol_exact,
    llms4ol_fuzzy,
    native_status,
)
from .provenance import runtime_versions, source_identity
from .reports import inspect_report
from .statistics import holm_adjust, paired_cluster_aggregate

ROOT = Path(__file__).resolve().parents[3]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load(path):
    return json.loads(Path(path).read_bytes())


def verify_assets(directory):
    directory = Path(directory).resolve(strict=True)
    manifest = load(directory / "asset-lock.json")
    for row in manifest["files"]:
        unresolved = directory / row["path"]
        path = unresolved.resolve(strict=True)
        if not path.is_relative_to(directory) or unresolved.is_symlink() or path.stat().st_size > 64_000_000 or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("ASSET_LOCK_MISMATCH")
    return {"status": "VERIFIED", "benchmark_id": manifest["benchmark_id"], "commit": manifest["commit"], "files": len(manifest["files"])}


def prepare(directory, output, *, task, limit, phase="smoke"):
    """Disjoint public inputs/private scoring targets. No gold-derived scope."""
    manifest = verify_assets(directory)
    if manifest["benchmark_id"] == "oskgc" and task == "schema_guided_abox":
        raise ValueError("BLOCKED_LICENSE_OSKGC_DATA_USE_NOT_AUTHORIZED")
    if manifest["benchmark_id"] == "cq4oe_0_0_1" and task in {"cq2term", "cq2onto"}:
        return prepare_cq4oe(directory, output, task=task, limit=limit)
    if manifest["benchmark_id"] != "llms4ol_2026" or manifest["commit"] != LLMS4OL_COMMIT:
        raise ValueError("INPUT_ADAPTER_NOT_YET_AUDITED_FOR_THIS_BENCHMARK")
    if phase != "smoke" or limit is None:
        return prepare_llms4ol_partition(directory, output, task=task, phase=phase)
    filename = "2026/TaskA-Flagship/train_task_a.json" if task == "flagship" else "2026/TaskB-Reuse/train_task_b.json"
    source = load(Path(directory) / filename)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    # Groups are hashes of normalized source documents, not triples or calls.
    # Choose the held-out partition and smoke subset without consulting targets.
    groups, selected = set(), []
    for record in sorted(source, key=lambda r: hashlib.sha256(r["id"].encode()).hexdigest()):
        sample = adapt_llms4ol(record, task=task)
        if int(sample.group_id[:8], 16) % 5 != 0 or sample.group_id in groups:
            continue
        groups.add(sample.group_id)
        selected.append((record, sample))
        if len(selected) == limit:
            break
    if not selected:
        raise ValueError("NO_HELD_OUT_SAMPLES")
    samples = [sample.model_dump(mode="json") for _, sample in selected]
    # Separate scoring extraction does not feed any generation field.
    targets = {sample.sample_id: record["primitive-ontology-triples" if task == "flagship" else "extended-primitive-ontology-triples"] for record, sample in selected}
    save(output / "generation/inputs.json", samples)
    save(output / "scoring/gold.json", targets)
    lock = {"benchmark_id": manifest["benchmark_id"], "dataset_version": manifest["commit"], "task_id": task,
        "evaluation_scope": "LOCAL_HOLDOUT", "input_sha256": semantic_hash(samples), "grouping": "NORMALIZED_DOCUMENT_SHA256",
        "selection": "SHA256(id) order; group hash modulo 5 == 0; first bounded independent groups",
        "sample_count": len(samples), "generation_files": ["generation/inputs.json"], "scorer_only_files": ["scoring/gold.json"],
        "gold_sha256": semantic_hash(targets), "source_file_sha256": hashlib.sha256((Path(directory) / filename).read_bytes()).hexdigest(),
        "pretraining_contamination": "POSSIBLE_PUBLIC_DATA", "smoke_subset_not_full_benchmark": True}
    save(output / "prepared-lock.json", lock)
    return {"status": "PREPARED", "sample_count": len(samples), "input_sha256": lock["input_sha256"]}


def prepare_llms4ol_partition(directory, output, *, task, phase):
    from .splits import group_public_documents, phase_for_group

    if phase not in {"smoke", "pilot", "full"} or task not in {"flagship", "reuse"}:
        raise ValueError("INVALID_PARTITION_TASK_OR_PHASE")
    verify_assets(directory)
    sources = {"flagship": "2026/TaskA-Flagship/train_task_a.json", "reuse": "2026/TaskB-Reuse/train_task_b.json"}
    raw = {name: load(Path(directory) / path) for name, path in sources.items()}
    public = [{"key": name + ":" + r["id"], "text": r["context"], "source": r["id"]} for name in sources for r in raw[name]]
    grouping = group_public_documents(public)
    split_rows = [{"key": r["key"], "group_id": grouping["groups"][r["key"]],
        "phase": phase_for_group(grouping["groups"][r["key"]])} for r in public]
    selected = []
    for record in raw[task]:
        group = grouping["groups"][task + ":" + record["id"]]
        if phase_for_group(group) == phase:
            sample = adapt_llms4ol(record, task=task).model_copy(update={"group_id": group})
            selected.append((record, sample))
    samples = [sample.model_dump(mode="json") for _, sample in selected]
    targets = {s.sample_id: r["primitive-ontology-triples" if task == "flagship" else "extended-primitive-ontology-triples"] for r, s in selected}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    save(output / "generation/inputs.json", samples)
    save(output / "scoring/gold.json", targets)
    save(output / "split-manifest.json", split_rows)
    save(output / "source-near-duplicate-audit.json", grouping)
    lock = {"benchmark_id": "llms4ol_2026", "dataset_version": LLMS4OL_COMMIT, "task_id": task,
        "evaluation_scope": "LOCAL_HOLDOUT", "phase": phase, "input_sha256": semantic_hash(samples), "gold_sha256": semantic_hash(targets),
        "sample_count": len(samples), "group_count": len({s.group_id for _, s in selected}), "source_count": len(raw[task]),
        "grouping": grouping["policy"], "split_sha256": semantic_hash(split_rows), "near_duplicate_audit_sha256": semantic_hash(grouping),
        "selection": "ALL_RECORDS_IN_PREDECLARED_PUBLIC_GROUP_HASH_PARTITION_NO_LIMIT", "phase_policy": "hash%10:0=smoke,1=pilot,2..9=full",
        "generation_files": ["generation/inputs.json"], "scorer_only_files": ["scoring/gold.json"],
        "source_files": {path: hashlib.sha256((Path(directory) / path).read_bytes()).hexdigest() for path in sources.values()},
        "smoke_subset_not_full_benchmark": phase != "full", "scope_label": "FULL_LOCAL_HOLDOUT" if phase == "full" else phase.upper(),
        "pretraining_contamination": "POSSIBLE_PUBLIC_DATA_CONTAMINATION",
        "historical_development_overlap": "NOT_YET_CLEARED_DO_NOT_CLAIM_STRONG_HOLDOUT"}
    save(output / "prepared-lock.json", lock)
    return {"status": "PREPARED", "sample_count": len(samples), "group_count": lock["group_count"], "input_sha256": lock["input_sha256"]}


def prepare_oskgc(directory, output, *, limit):
    from defusedxml import ElementTree as ET

    from .oskgc import OSKGC_COMMIT, adapt_oskgc, scoring_target

    verify_assets(directory)
    asset = load(Path(directory) / "asset-lock.json")
    if asset["commit"] != OSKGC_COMMIT:
        raise ValueError("OSKGC_REVISION_MISMATCH")
    selected, groups, source_hashes = [], set(), {}
    # Only the fetched Airport subset and public TRAIN partition. Never mix
    # dev/test into a train-derived holdout or use per-entry schema as input.
    records = []
    for row in asset["files"]:
        if row["path"].startswith("benchmark/data/train/") and row["path"].endswith("_Airport.xml"):
            source_hashes[row["path"]] = row["sha256"]
            records.extend(ET.fromstring((Path(directory) / row["path"]).read_bytes()).findall("entries/entry"))
    for entry in sorted(records, key=lambda r: hashlib.sha256(r.attrib["id"].encode()).hexdigest()):
        category = entry.attrib["category"]
        name = "benchmark/ontology/" + category + ".json"
        declaration = next((r for r in asset["files"] if r["path"] == name), None)
        if declaration is None:
            raise ValueError("OSKGC_CATEGORY_SCHEMA_NOT_LOCKED")
        schema = load(Path(directory) / name)
        source_hashes[name] = declaration["sha256"]
        sample = adapt_oskgc(entry, schema)
        if int(sample.group_id[:8], 16) % 5 != 0 or sample.group_id in groups:
            continue
        groups.add(sample.group_id)
        selected.append((entry, sample))
        if len(selected) == limit:
            break
    if not selected:
        raise ValueError("NO_HELD_OUT_SAMPLES")
    samples = [s.model_dump(mode="json") for _, s in selected]
    targets = {s.sample_id: scoring_target(entry) for entry, s in selected}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    save(output / "generation/inputs.json", samples)
    save(output / "scoring/gold.json", targets)
    lock = {"benchmark_id": "oskgc", "dataset_version": OSKGC_COMMIT, "task_id": "schema_guided_abox", "evaluation_scope": "LOCAL_HOLDOUT",
        "input_sha256": semantic_hash(samples), "gold_sha256": semantic_hash(targets), "source_files": source_hashes,
        "sample_count": len(samples), "grouping": "NORMALIZED_DOCUMENT_SHA256", "selection": "TRAIN_ONLY; SHA256(id) order; group hash modulo 5 == 0",
        "generation_files": ["generation/inputs.json"], "scorer_only_files": ["scoring/gold.json"], "smoke_subset_not_full_benchmark": True,
        "data_export_policy": "RESEARCH_ONLY_NO_COMMERCIAL_DELIVERY_LICENCE_CONFLICT", "pretraining_contamination": "POSSIBLE_PUBLIC_DATA"}
    save(output / "prepared-lock.json", lock)
    return {"status": "PREPARED", "sample_count": len(samples), "input_sha256": lock["input_sha256"], "generation_profile": "BLOCKED_TYPED_ARTIFACT_ADAPTER_NOT_INTEGRATED"}


def prepare_cq4oe(directory, output, *, task, limit):
    from .cq4oe import CQ4OE_COMMIT, adapt_cq4oe

    verify_assets(directory)
    asset = load(Path(directory) / "asset-lock.json")
    if asset["commit"] != CQ4OE_COMMIT:
        raise ValueError("CQ4OE_REVISION_MISMATCH")
    input_directory = PurePosixPath("CQ2Term" if task == "cq2term" else "CQ2Onto") / "competency_question"
    declarations = sorted((r for r in asset["files"] if PurePosixPath(r["path"]).parent == input_directory
        and PurePosixPath(r["path"]).suffix == ".json"), key=lambda r: r["path"])[:limit]
    if not declarations:
        raise ValueError("CQ4OE_INPUT_ASSETS_MISSING")
    samples = [adapt_cq4oe(load(Path(directory) / row["path"]), sample_id=Path(row["path"]).stem, task=task).model_dump(mode="json") for row in declarations]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    save(output / "generation/inputs.json", samples)
    lock = {"benchmark_id": "cq4oe_0_0_1", "dataset_version": CQ4OE_COMMIT, "task_id": task, "evaluation_scope": "ADAPTED_ANALYSIS",
        "input_sha256": semantic_hash(samples), "sample_count": len(samples), "grouping": "WHOLE_ONTOLOGY_CQ_SET",
        "selection": "ALL_LOCKED_CQ_DOCUMENTS" if limit is None else "SORTED_LOCKED_INPUT_FILENAMES_BOUNDED_SUBSET_NO_GOLD_SELECTION", "source_files": declarations,
        "generation_files": ["generation/inputs.json"], "scorer_only_files": [], "gold_sha256": None,
        "scorer_status": "NOT_PREPARED_NATIVE_ALIGNMENT_AND_REASONER_PROFILE_NOT_YET_AUDITED",
        "abox": "NOT_APPLICABLE_NO_INSTANCES", "smoke_subset_not_full_benchmark": limit is not None,
        "scope_label": "ALL_PUBLIC_ONTOLOGIES_NOT_OFFICIAL_TEST" if limit is None else "SMOKE",
        "group_count": len(samples), "ontologies": [s["sample_id"] for s in samples]}
    if task == "cq2term":
        targets = {}
        for sample in samples:
            name = sample["sample_id"].split("_")[0]
            path = f"CQ2Term/00_gold_standard/{name}/cq_to_terms_{name}.json"
            if not any(r["path"] == path for r in asset["files"]):
                # Keep input-only preparation for audited input fixtures.
                targets = {}
                break
            targets[sample["sample_id"]] = load(Path(directory) / path)
        if targets:
            save(output / "scoring/gold.json", targets)
            lock.update(gold_sha256=semantic_hash(targets), scorer_only_files=["scoring/gold.json"],
                scorer_status="NATIVE_HARD_TERM_METHOD_ONLY_FULL_TOP3_ALIGNMENT_BLOCKED")
    save(output / "prepared-lock.json", lock)
    return {"status": "PREPARED_INPUTS_ONLY", "sample_count": len(samples), "input_sha256": lock["input_sha256"], "native_score": None,
        "generation_profile": "BLOCKED_NATIVE_TBOX_ARTIFACT_ADAPTER_NOT_INTEGRATED"}


def run(prepared, protocol_path, output, *, system, dry_run):
    prepared, output = Path(prepared), Path(output)
    protocol = Protocol.model_validate(yaml.safe_load(Path(protocol_path).read_text(encoding="utf-8")))
    if system not in protocol.systems:
        raise ValueError("SYSTEM_NOT_IN_FROZEN_PROTOCOL")
    raw_inputs = load(prepared / "generation/inputs.json")
    lock = load(prepared / "prepared-lock.json")
    if semantic_hash(raw_inputs) != lock["input_sha256"]:
        raise ValueError("PREPARED_INPUT_CHANGED")
    samples = [ModelingInput.model_validate(row) for row in raw_inputs]
    if not samples or len({s.sample_id for s in samples}) != len(samples):
        raise ValueError("EMPTY_OR_DUPLICATE_INPUTS")
    if not dry_run:
        required_calls = len(samples) * protocol.replicates * (1 if system == "DirectGeneralLLM" else protocol.budget.max_calls)
        required_tokens = len(samples) * protocol.replicates * protocol.budget.max_total_tokens
        authorization = protocol.total_run_authorization
        if not authorization:
            raise ValueError("BLOCKED_BUDGET_UNSET")
        if (not authorization.get("user_authorization_ref") or authorization.get("max_calls", 0) < required_calls
                or authorization.get("max_tokens", 0) < required_tokens):
            raise ValueError("BLOCKED_TOTAL_BUDGET_INSUFFICIENT")
        # Current CLI has no verified restricted process launcher. Do not let
        # the historical run entry point bypass the full-matrix isolation gate.
        from .isolation import require_isolation
        require_isolation(None)
    identity = source_identity(ROOT)
    output.mkdir(parents=True, exist_ok=False)
    # This process deliberately never opens scoring/gold.json. A hardened
    # container mount is a separate prerequisite, not falsely claimed here.
    report = {"run_id": "io-run-" + uuid4().hex, "system_id": system, "protocol": protocol.model_dump(mode="json"),
        "protocol_sha256": semantic_hash(protocol.model_dump(mode="json")), "input_sha256": lock["input_sha256"],
        "samples": [], "status": "DRY_RUN" if dry_run else "RUNNING", "research_score": None,
        "isolation": "CLOSED_INPUT_AND_TOOL_BROKER_NOT_OS_SANDBOX", "mode": "BENCHMARK_DRAFT",
        "source_commit": identity["commit"], "source_fingerprint_sha256": identity["fingerprint"]["digest"],
        "source_identity": identity, "generation_runtime": runtime_versions()}
    save(output / "generation-inputs.json", raw_inputs)
    if not dry_run:
        for sample in samples:
            for replicate in range(protocol.replicates):
                name = f"{sample.sample_id}-{replicate}"
                generated = generate_sample(sample, protocol, system, output / name, replicate_id=replicate)
                report["samples"].append({"sample_id": sample.sample_id, "group_id": sample.group_id, "replicate_id": replicate,
                    "path": name, "status": generated["status"], "result_sha256": semantic_hash(generated)})
                save(output / "run.json", report)
        report["source_unchanged"] = source_identity(ROOT) == identity
        report["status"] = "FROZEN_PREDICTIONS" if report["source_unchanged"] else "INVALID_SOURCE_CHANGED"
    save(output / "run.json", report)
    return {"status": report["status"], "run_id": report["run_id"], "score": None}


def verify_sample_inventory(manifest, inputs, protocol):
    # Historical protocols did not serialize newer optional fields. Validate
    # with today's contract but hash the ACTUAL frozen document, not defaults.
    if manifest["protocol_sha256"] != semantic_hash(manifest.get("protocol", protocol.model_dump(mode="json"))):
        raise ValueError("FROZEN_PROTOCOL_CHANGED")
    expected = {(sample_id, replicate) for sample_id in inputs for replicate in range(protocol.replicates)}
    actual = [(row["sample_id"], row["replicate_id"]) for row in manifest["samples"]]
    if set(actual) != expected or len(actual) != len(expected):
        raise ValueError("PREDICTION_INVENTORY_INCOMPLETE_OR_DUPLICATED")
    for row in manifest["samples"]:
        if row["path"] != f"{row['sample_id']}-{row['replicate_id']}" or row["group_id"] != inputs[row["sample_id"]].group_id:
            raise ValueError("PREDICTION_PATH_OR_GROUP_CHANGED")


def score(run_dir, prepared, upstream, output, *, framework="native"):
    """A separate scoring invocation, called only after predictions freeze."""
    run_dir, prepared = Path(run_dir), Path(prepared)
    manifest = load(run_dir / "run.json")
    if manifest["status"] != "FROZEN_PREDICTIONS":
        raise ValueError("PREDICTIONS_NOT_FROZEN")
    protocol = Protocol.model_validate(manifest["protocol"])
    if native_status(protocol.matching) != "READY":
        raise ValueError(native_status(protocol.matching))
    lock = load(prepared / "prepared-lock.json")
    benchmark = lock["benchmark_id"]
    if framework not in {"native", "deepeval"}:
        raise ValueError("UNKNOWN_SCORING_FRAMEWORK")
    framework_scorer = None
    if framework == "deepeval":
        if benchmark != "llms4ol_2026":
            raise ValueError("DEEPEVAL_BRIDGE_ONLY_SUPPORTS_PINNED_LLMS4OL_GRAPH_METRICS")
        from .deepeval_bridge import native_llms4ol_scorer
        framework_scorer = native_llms4ol_scorer(upstream, matching=protocol.matching)
    if benchmark == "cq4oe_0_0_1" and lock["task_id"] == "cq2onto":
        raise ValueError("BLOCKED_CQ4OE_NATIVE_ALIGNMENT_REASONER_AXIOM_PROFILE")
    if benchmark == "oskgc" and not lock.get("data_use_authorization") and lock["evaluation_scope"] != "ENGINEERING_CHECK":
        raise ValueError("BLOCKED_LICENSE_OSKGC_DATA_USE_NOT_AUTHORIZED")
    if benchmark not in {"llms4ol_2026", "cq4oe_0_0_1", "oskgc"}:
        raise ValueError("NATIVE_SCORER_NOT_INTEGRATED_WITH_FROZEN_RUN_PROFILE")
    if benchmark != "llms4ol_2026" and protocol.matching != "exact":
        raise ValueError("MATCHER_NOT_SUPPORTED_BY_TASK_PROFILE")
    gold = load(prepared / "scoring/gold.json")
    if semantic_hash(gold) != lock["gold_sha256"] or manifest["input_sha256"] != lock["input_sha256"]:
        raise ValueError("SCORER_INPUT_OR_GOLD_CHANGED")
    generation_inputs = load(run_dir / "generation-inputs.json")
    if semantic_hash(generation_inputs) != manifest["input_sha256"]:
        raise ValueError("GENERATION_INPUT_COPY_CHANGED")
    inputs = {s["sample_id"]: ModelingInput.model_validate(s) for s in generation_inputs}
    frozen_input_rows = {s["sample_id"]: s for s in generation_inputs}
    if len(inputs) != len(generation_inputs) or len(inputs) != lock["sample_count"]:
        raise ValueError("PREPARED_SAMPLE_INVENTORY_CHANGED")
    verify_sample_inventory(manifest, inputs, protocol)
    rows, resources, models = [], [], set()
    for entry in manifest["samples"]:
        sample = inputs[entry["sample_id"]]
        result = load(run_dir / entry["path"] / "result.json")
        if semantic_hash(result) != entry["result_sha256"]:
            raise ValueError("FROZEN_PREDICTION_CHANGED")
        if any(result[key] != value for key, value in {
            "sample_id": sample.sample_id, "group_id": sample.group_id, "replicate_id": entry["replicate_id"],
            "system_id": manifest["system_id"], "protocol_sha256": manifest["protocol_sha256"],
            "input_sha256": semantic_hash(frozen_input_rows[sample.sample_id]), "status": entry["status"],
        }.items()):
            raise ValueError("FROZEN_RESULT_CONTEXT_CHANGED")
        resources.append(result["resources"])
        models.update(c.get("model", {}).get("observed_model_id", c.get("model", {}).get("model_id", "UNKNOWN")) for c in result["calls"])
        row = {"sample_id": sample.sample_id, "group_id": sample.group_id, "replicate_id": entry["replicate_id"], "status": "UNSCORABLE", "metrics": None,
            "generation_status": result["status"], "failure_type": result.get("failure_type"), "failure_code": result.get("failure_code"),
            "raw_result_sha256": entry["result_sha256"], "raw_result_ref": entry["path"] + "/result.json"}
        if result["status"] == "GENERATED":
            if load(run_dir / entry["path"] / "artifacts/projection.json") != result["prediction"]:
                raise ValueError("FROZEN_PROJECTION_CHANGED")
            projected = project_task_prediction(run_dir / entry["path"] / "artifacts", sample)
            expected = gold[sample.sample_id]
            if sample.task_id == "reuse":
                expected = additions_only(expected, sample.initial_triples)
            if benchmark == "llms4ol_2026":
                scorer = llms4ol_exact if protocol.matching == "exact" else llms4ol_fuzzy
                values = framework_scorer(expected, projected["triples"]) if framework_scorer else scorer(upstream, expected, projected["triples"])
            elif benchmark == "cq4oe_0_0_1":
                from .cq4oe import native_term_hard
                values = {}
                for role in ("classes", "properties"):
                    prediction_terms = sorted({v.strip().lower() for r in projected["cq_terms"] for v in r[role] if v.strip()})
                    target_terms = sorted({v.strip().lower() for r in expected for v in r[role] if v.strip()})
                    values.update({role + "_" + k: v for k, v in native_term_hard(upstream, prediction_terms, target_terms).items()})
            else:
                values = {}  # Filled by native full-run aggregate below.
            row.update(status="MEASURED", metrics=values, projection=projected)
        rows.append(row)
    complete = bool(rows) and all(row["status"] == "MEASURED" for row in rows)
    names = ["edge_f1", "neighborhood_similarity", "taxonomy_similarity", "graph_similarity"]
    native_commit, native_hash = LLMS4OL_COMMIT, LLMS4OL_SCORER_SHA256
    metric_source = "LLMs4OL_2026_PINNED_FUNCTIONS_LOCAL_SAMPLE_MEAN_NOT_OFFICIAL_RANKING"
    aggregation = "LOCAL_SAMPLE_MEAN"
    aggregate_values = None
    if benchmark == "cq4oe_0_0_1":
        from .cq4oe import CQ4OE_COMMIT, TERM_SCORER_SHA256
        native_commit, native_hash = CQ4OE_COMMIT, TERM_SCORER_SHA256
        names = [role + "_" + metric for role in ("classes", "properties") for metric in ("precision", "recall", "f1", "coverage")]
        metric_source = "CQ4OE_NATIVE_PER_METHOD_HARD_TERMS_ONLY_NOT_FULL_TOP3_ALIGNMENT"
    elif benchmark == "oskgc":
        from .oskgc import (
            OSKGC_COMMIT,
            OSKGC_SCORER_SHA256,
            hierarchy_from_bytes,
            score_native,
        )
        native_commit, native_hash = OSKGC_COMMIT, OSKGC_SCORER_SHA256
        names = ["Precision", "Recall", "micro_F1", "macro_F1", "SS"]
        metric_source = "OSKGC_PINNED_NATIVE_GLOBAL_SET_MICRO_FILE_ROUNDED_MACRO_SS"
        aggregation = "NATIVE_AGGREGATE_EACH_REPLICATE_THEN_MEAN"
        if complete:
            raw = (Path(upstream) / "evaluator/base_evaluator.py").read_bytes()
            hierarchy = hierarchy_from_bytes((Path(upstream) / "benchmark/hierarchy.xml").read_bytes())
            repeats = []
            for rep in range(protocol.replicates):
                predictions = {r["sample_id"]: r["projection"] for r in rows if r["replicate_id"] == rep}
                scored = score_native(raw, predictions, gold, hierarchy)
                repeats.append(scored["metrics"])
                for r in rows:
                    if r["replicate_id"] == rep:
                        r["metrics"] = next(s for s in scored["samples"] if s["sample_id"] == r["sample_id"])
            aggregate_values = {name: mean(r[name] for r in repeats) for name in names}
    metrics = [{"name": name, "source": metric_source, "matching": "hard_match" if benchmark == "cq4oe_0_0_1" else protocol.matching,
        "value": (aggregate_values[name] if aggregate_values else mean(row["metrics"][name] for row in rows)) if complete else None, "unit": "fraction", "numerator": None, "denominator": len(rows),
        "status": "MEASURED" if complete else "UNSCORABLE", "sample_count": len(rows),
        "failure_count": sum(row["status"] != "MEASURED" for row in rows)} for name in names]
    scorer_runtime = runtime_versions()
    report = {"schema_version": "1.0.0", **{k: lock[k] for k in ("benchmark_id", "task_id", "dataset_version", "evaluation_scope")},
        "split": next(iter(inputs.values())).split, "input_manifest_sha256": manifest["input_sha256"], "prediction_manifest_sha256": semantic_hash(manifest),
        "scorer_commit": native_commit, "scorer_config_sha256": semantic_hash({"matching": protocol.matching,
            "aggregation": aggregation, "projection": "task-typed-research-draft-v1",
            "scorer_sha256": native_hash, "runtime": scorer_runtime, "framework": framework,
            "framework_version": "4.1.0" if framework == "deepeval" else None}), "system_id": manifest["system_id"], "aggregation": aggregation,
        "scoring_framework": framework,
        "scorer_runtime": scorer_runtime, "generation_runtime": manifest["generation_runtime"],
        "protocol": manifest["protocol"], "protocol_sha256": manifest["protocol_sha256"],
        "model_id": protocol.model_id, "declared_revision": protocol.declared_revision, "observed_model_ids": sorted(models), "run_id": manifest["run_id"],
        "source_commit": manifest["source_commit"], "source_fingerprint_sha256": manifest["source_fingerprint_sha256"],
        "metrics": metrics, "sample_count": len(rows), "failure_count": sum(row["status"] != "MEASURED" for row in rows),
        "status": "MEASURED" if complete else "UNSCORABLE", "comparison": None, "resources": resources, "samples": rows,
        "limitations": [lock.get("scope_label", "Small local smoke subset") + "; not an official test result", "Exact scorer has zero taxonomy component for graphs without taxonomy",
            "Public pretraining contamination possible", "Semantic matching and official ranking configuration not yet independently locked",
            "Primitive pilot is not a completed full TwoAgentV3 implementation", "No expert evaluation or project accuracy attainment claim"]}
    Draft202012Validator(REPORT_SCHEMA).validate(report)
    if benchmark != "llms4ol_2026":
        report["limitations"] = ["Research draft; no approval or formal v3 export", "No full Ours or expert comparison",
            "POSSIBLE_PUBLIC_DATA_CONTAMINATION", "Only stated task-native metric profile is measured, not other benchmarks",
            "CQ4OE hard per-method terms is not full top3/semantic/axiom/CQCoverage" if benchmark == "cq4oe_0_0_1" else "OSKGC data-use authorization must be separately resolved"]
    save(Path(output), report)
    return {"status": report["status"], "samples": len(rows), "failed": report["failure_count"]}


def compare(left, right, output):
    a, b = load(left), load(right)
    if any(r.get("aggregation") == "NATIVE_AGGREGATE_EACH_REPLICATE_THEN_MEAN" for r in (a, b)):
        raise ValueError("NONADDITIVE_COMPARISON_REQUIRES_NATIVE_PAYLOAD_CLUSTER_AGGREGATOR_NOT_SAMPLE_MEAN")
    for report in (a, b):
        inspect_report(report, max_bytes=64_000_000)
    for field in ("model_id", "declared_revision", "observed_model_ids", "benchmark_id", "task_id", "dataset_version", "split", "evaluation_scope",
                  "input_manifest_sha256", "scorer_commit", "scorer_config_sha256", "protocol_sha256", "source_fingerprint_sha256"):
        if a[field] != b[field]:
            raise ValueError("COMPARISON_NOT_PAIRED:" + field)
    if a["status"] != "MEASURED" or b["status"] != "MEASURED":
        raise ValueError("CANNOT_COMPARE_SUCCESS_SUBSETS")
    protocol = Protocol.model_validate(a["protocol"])
    if a["protocol"] != b["protocol"] or semantic_hash(a["protocol"]) != a["protocol_sha256"]:
        raise ValueError("FROZEN_PROTOCOL_CHANGED")
    if a["run_id"] == b["run_id"]:
        raise ValueError("CANNOT_COMPARE_RUN_WITH_ITSELF")
    paired_ids = []
    for report in (a, b):
        ids = [(r["sample_id"], r["group_id"], r["replicate_id"]) for r in report["samples"]]
        if len(set(ids)) != len(ids) or len(ids) != report["sample_count"] or any(r["status"] != "MEASURED" for r in report["samples"]):
            raise ValueError("INVALID_COMPARISON_SAMPLE_INVENTORY")
        paired_ids.append(set(ids))
    if paired_ids[0] != paired_ids[1]:
        raise ValueError("PAIRED_SAMPLE_OR_REPLICATE_IDS_DIFFER")
    names = [row["name"] for row in a["metrics"]]
    if set(names) != {row["name"] for row in b["metrics"]} or not set(protocol.primary_metrics) <= set(names):
        raise ValueError("PREREGISTERED_METRIC_NOT_PRESENT")
    metrics = {}
    for metric in names:
        groups = []
        for report in (a, b):
            grouped = defaultdict(lambda: defaultdict(list))
            for row in report["samples"]:
                grouped[row["group_id"]][row["replicate_id"]].append(row["metrics"][metric])
            groups.append(grouped)
        metrics[metric] = paired_cluster_aggregate(*groups, aggregate=mean, bootstrap_samples=protocol.bootstrap_samples, seed=protocol.statistics_seed)
    family = {name: metrics[name]["p_value"] for name in protocol.primary_metrics if metrics[name]["p_value"] is not None}
    adjusted = holm_adjust(family) if len(family) == len(protocol.primary_metrics) else {}
    for name, value in metrics.items():
        value.update(primary=name in protocol.primary_metrics, adjusted_p_value=adjusted.get(name),
            correction="HOLM_PRIMARY_FAMILY" if name in protocol.primary_metrics else "EXPLORATORY_UNCORRECTED")
    comparison = {"baseline_run": a["run_id"], "experiment_run": b["run_id"], "metrics": metrics,
        "baseline_report_sha256": semantic_hash(a), "experiment_report_sha256": semantic_hash(b),
        "primary_metrics": protocol.primary_metrics, "primary_test_correction": protocol.primary_test_correction,
        "conclusion": "EXPLORATORY_SMOKE_NOT_EVIDENCE_OF_GENERAL_SUPERIORITY", "project_goals": "INSUFFICIENT_EVIDENCE"}
    result = {**b, "comparison": comparison}
    Draft202012Validator(REPORT_SCHEMA).validate(result)
    save(Path(output), result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify-assets"); verify.add_argument("directory", type=Path)
    prep = sub.add_parser("prepare-inputs"); prep.add_argument("directory", type=Path); prep.add_argument("output", type=Path)
    prep.add_argument("--task", choices=["flagship", "reuse", "schema_guided_abox", "cq2term", "cq2onto"], required=True); prep.add_argument("--limit", type=int, default=3)
    prep.add_argument("--phase", choices=["smoke", "pilot", "full"], default="smoke")
    execute = sub.add_parser("run"); execute.add_argument("prepared", type=Path); execute.add_argument("protocol", type=Path); execute.add_argument("output", type=Path)
    execute.add_argument("--system", required=True); execute.add_argument("--dry-run", action="store_true")
    replay = sub.add_parser("replay", help="Run actual kernels with a frozen ENGINEERING_CHECK recording; never LIVE")
    replay.add_argument("input", type=Path); replay.add_argument("protocol", type=Path)
    replay.add_argument("recording", type=Path); replay.add_argument("output", type=Path); replay.add_argument("--system", required=True)
    replay.add_argument("--record-trace", action="store_true", help="Opt-in local content journal; replay is never an LLM event")
    scorer = sub.add_parser("score"); scorer.add_argument("run", type=Path); scorer.add_argument("prepared", type=Path); scorer.add_argument("upstream", type=Path); scorer.add_argument("output", type=Path)
    scorer.add_argument("--framework", choices=["native", "deepeval"], default="native", help="deepeval requires credential-free OFFLINE_SETTINGS; never an LLM judge")
    comparison = sub.add_parser("compare"); comparison.add_argument("baseline", type=Path); comparison.add_argument("experiment", type=Path); comparison.add_argument("output", type=Path)
    export = sub.add_parser("export"); export.add_argument("report", type=Path); export.add_argument("output", type=Path)
    schema = sub.add_parser("schema"); schema.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "verify-assets":
        result = verify_assets(args.directory)
    elif args.command == "prepare-inputs":
        if not 1 <= args.limit <= 1000:
            parser.error("limit must be 1..1000")
        result = prepare(args.directory, args.output, task=args.task, limit=None if args.phase != "smoke" else args.limit, phase=args.phase)
    elif args.command == "run":
        result = run(args.prepared, args.protocol, args.output, system=args.system, dry_run=args.dry_run)
    elif args.command == "replay":
        from .replay import replay_sample
        result = replay_sample(args.input, args.protocol, args.recording, args.output, system=args.system, record_trace=args.record_trace)
    elif args.command == "score":
        result = score(args.run, args.prepared, args.upstream, args.output, framework=args.framework)
    elif args.command == "compare":
        result = compare(args.baseline, args.experiment, args.output)
    elif args.command == "schema":
        save(args.output, REPORT_SCHEMA)
        result = {"status": "EXPORTED_SCHEMA", "path": str(args.output), "research_score": None}
    else:
        result = load(args.report)
        inspect_report(result, max_bytes=64_000_000)
        save(args.output, result)
    print(json.dumps(result, ensure_ascii=False))
    if args.command == "replay" and result["status"] != "GENERATED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
