"""Independent research CLI. Scoring never calls generation or changes predictions."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from uuid import uuid4

import yaml
from jsonschema import Draft202012Validator

from zhigou_toolchain.contracts.canonical import semantic_hash

from .adapters import adapt_llms4ol, additions_only, project_prediction
from .contracts import REPORT_SCHEMA, ModelingInput, Protocol
from .engine import generate_sample
from .native_metrics import (
    LLMS4OL_COMMIT,
    LLMS4OL_SCORER_SHA256,
    llms4ol_exact,
    native_status,
)
from .provenance import runtime_versions, source_identity
from .reports import inspect_report
from .statistics import holm_adjust, paired_comparison

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


def prepare(directory, output, *, task, limit):
    """Disjoint public inputs/private scoring targets. No gold-derived scope."""
    manifest = verify_assets(directory)
    if manifest["benchmark_id"] == "oskgc" and task == "schema_guided_abox":
        return prepare_oskgc(directory, output, limit=limit)
    if manifest["benchmark_id"] == "cq4oe_0_0_1" and task in {"cq2term", "cq2onto"}:
        return prepare_cq4oe(directory, output, task=task, limit=limit)
    if manifest["benchmark_id"] != "llms4ol_2026" or manifest["commit"] != LLMS4OL_COMMIT:
        raise ValueError("INPUT_ADAPTER_NOT_YET_AUDITED_FOR_THIS_BENCHMARK")
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
    prefix = ("CQ2Term" if task == "cq2term" else "CQ2Onto") + "/competency_question/"
    declarations = sorted((r for r in asset["files"] if r["path"].startswith(prefix) and r["path"].endswith(".json")), key=lambda r: r["path"])[:limit]
    if not declarations:
        raise ValueError("CQ4OE_INPUT_ASSETS_MISSING")
    samples = [adapt_cq4oe(load(Path(directory) / row["path"]), sample_id=Path(row["path"]).stem, task=task).model_dump(mode="json") for row in declarations]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    save(output / "generation/inputs.json", samples)
    lock = {"benchmark_id": "cq4oe_0_0_1", "dataset_version": CQ4OE_COMMIT, "task_id": task, "evaluation_scope": "ADAPTED_ANALYSIS",
        "input_sha256": semantic_hash(samples), "sample_count": len(samples), "grouping": "WHOLE_ONTOLOGY_CQ_SET",
        "selection": "SORTED_LOCKED_INPUT_FILENAMES_BOUNDED_SUBSET_NO_GOLD_SELECTION", "source_files": declarations,
        "generation_files": ["generation/inputs.json"], "scorer_only_files": [], "gold_sha256": None,
        "scorer_status": "NOT_PREPARED_NATIVE_ALIGNMENT_AND_REASONER_PROFILE_NOT_YET_AUDITED",
        "abox": "NOT_APPLICABLE_NO_INSTANCES", "smoke_subset_not_full_benchmark": True}
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
    if manifest["protocol_sha256"] != semantic_hash(protocol.model_dump(mode="json")):
        raise ValueError("FROZEN_PROTOCOL_CHANGED")
    expected = {(sample_id, replicate) for sample_id in inputs for replicate in range(protocol.replicates)}
    actual = [(row["sample_id"], row["replicate_id"]) for row in manifest["samples"]]
    if set(actual) != expected or len(actual) != len(expected):
        raise ValueError("PREDICTION_INVENTORY_INCOMPLETE_OR_DUPLICATED")
    for row in manifest["samples"]:
        if row["path"] != f"{row['sample_id']}-{row['replicate_id']}" or row["group_id"] != inputs[row["sample_id"]].group_id:
            raise ValueError("PREDICTION_PATH_OR_GROUP_CHANGED")


def score(run_dir, prepared, upstream, output):
    """A separate scoring invocation, called only after predictions freeze."""
    run_dir, prepared = Path(run_dir), Path(prepared)
    manifest = load(run_dir / "run.json")
    if manifest["status"] != "FROZEN_PREDICTIONS":
        raise ValueError("PREDICTIONS_NOT_FROZEN")
    protocol = Protocol.model_validate(manifest["protocol"])
    if native_status(protocol.matching) != "READY":
        raise ValueError(native_status(protocol.matching))
    lock = load(prepared / "prepared-lock.json")
    if lock["benchmark_id"] != "llms4ol_2026":
        raise ValueError("NATIVE_SCORER_NOT_INTEGRATED_WITH_FROZEN_RUN_PROFILE")
    gold = load(prepared / "scoring/gold.json")
    if semantic_hash(gold) != lock["gold_sha256"] or manifest["input_sha256"] != lock["input_sha256"]:
        raise ValueError("SCORER_INPUT_OR_GOLD_CHANGED")
    generation_inputs = load(run_dir / "generation-inputs.json")
    if semantic_hash(generation_inputs) != manifest["input_sha256"]:
        raise ValueError("GENERATION_INPUT_COPY_CHANGED")
    inputs = {s["sample_id"]: ModelingInput.model_validate(s) for s in generation_inputs}
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
            "input_sha256": semantic_hash(sample.model_dump(mode="json")), "status": entry["status"],
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
            projected = project_prediction(run_dir / entry["path"] / "artifacts", sample)
            expected = gold[sample.sample_id]
            if sample.task_id == "reuse":
                expected = additions_only(expected, sample.initial_triples)
            row.update(status="MEASURED", metrics=llms4ol_exact(upstream, expected, projected["triples"]), projection=projected)
        rows.append(row)
    complete = bool(rows) and all(row["status"] == "MEASURED" for row in rows)
    names = ["edge_f1", "neighborhood_similarity", "taxonomy_similarity", "graph_similarity"]
    metrics = [{"name": name, "source": "LLMs4OL_2026_PINNED_EXACT_FUNCTIONS_LOCAL_SAMPLE_MEAN_NOT_OFFICIAL_RANKING", "matching": "exact",
        "value": mean(row["metrics"][name] for row in rows) if complete else None, "unit": "fraction", "numerator": None, "denominator": len(rows),
        "status": "MEASURED" if complete else "UNSCORABLE", "sample_count": len(rows),
        "failure_count": sum(row["status"] != "MEASURED" for row in rows)} for name in names]
    scorer_runtime = runtime_versions()
    report = {"schema_version": "1.0.0", **{k: lock[k] for k in ("benchmark_id", "task_id", "dataset_version", "evaluation_scope")},
        "split": "LOCAL_HOLDOUT", "input_manifest_sha256": manifest["input_sha256"], "prediction_manifest_sha256": semantic_hash(manifest),
        "scorer_commit": LLMS4OL_COMMIT, "scorer_config_sha256": semantic_hash({"matching": protocol.matching,
            "aggregation": "LOCAL_SAMPLE_MEAN", "projection": "primitive-v3-native-exact-relations",
            "scorer_sha256": LLMS4OL_SCORER_SHA256, "runtime": scorer_runtime}), "system_id": manifest["system_id"],
        "scorer_runtime": scorer_runtime, "generation_runtime": manifest["generation_runtime"],
        "protocol": protocol.model_dump(mode="json"), "protocol_sha256": manifest["protocol_sha256"],
        "model_id": protocol.model_id, "declared_revision": protocol.declared_revision, "observed_model_ids": sorted(models), "run_id": manifest["run_id"],
        "source_commit": manifest["source_commit"], "source_fingerprint_sha256": manifest["source_fingerprint_sha256"],
        "metrics": metrics, "sample_count": len(rows), "failure_count": sum(row["status"] != "MEASURED" for row in rows),
        "status": "MEASURED" if complete else "UNSCORABLE", "comparison": None, "resources": resources, "samples": rows,
        "limitations": ["Small local smoke subset, not an official test result", "Exact scorer has zero taxonomy component for graphs without taxonomy",
            "Public pretraining contamination possible", "Semantic matching and official ranking configuration not yet independently locked",
            "Primitive pilot is not a completed full TwoAgentV3 implementation", "No expert evaluation or project accuracy attainment claim"]}
    Draft202012Validator(REPORT_SCHEMA).validate(report)
    save(Path(output), report)
    return {"status": report["status"], "samples": len(rows), "failed": report["failure_count"]}


def compare(left, right, output):
    a, b = load(left), load(right)
    for report in (a, b):
        inspect_report(report, max_bytes=64_000_000)
    for field in ("model_id", "declared_revision", "observed_model_ids", "benchmark_id", "task_id", "dataset_version", "split", "evaluation_scope",
                  "input_manifest_sha256", "scorer_commit", "scorer_config_sha256", "protocol_sha256", "source_fingerprint_sha256"):
        if a[field] != b[field]:
            raise ValueError("COMPARISON_NOT_PAIRED:" + field)
    if a["status"] != "MEASURED" or b["status"] != "MEASURED":
        raise ValueError("CANNOT_COMPARE_SUCCESS_SUBSETS")
    protocol = Protocol.model_validate(a["protocol"])
    if a["protocol"] != b["protocol"] or semantic_hash(protocol.model_dump(mode="json")) != a["protocol_sha256"]:
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
            grouped = defaultdict(list)
            for row in report["samples"]:
                grouped[row["group_id"]].append(row["metrics"][metric])
            groups.append(grouped)
        metrics[metric] = paired_comparison(*groups, bootstrap_samples=protocol.bootstrap_samples, seed=protocol.statistics_seed)
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
    execute = sub.add_parser("run"); execute.add_argument("prepared", type=Path); execute.add_argument("protocol", type=Path); execute.add_argument("output", type=Path)
    execute.add_argument("--system", required=True); execute.add_argument("--dry-run", action="store_true")
    scorer = sub.add_parser("score"); scorer.add_argument("run", type=Path); scorer.add_argument("prepared", type=Path); scorer.add_argument("upstream", type=Path); scorer.add_argument("output", type=Path)
    comparison = sub.add_parser("compare"); comparison.add_argument("baseline", type=Path); comparison.add_argument("experiment", type=Path); comparison.add_argument("output", type=Path)
    export = sub.add_parser("export"); export.add_argument("report", type=Path); export.add_argument("output", type=Path)
    schema = sub.add_parser("schema"); schema.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    if args.command == "verify-assets":
        result = verify_assets(args.directory)
    elif args.command == "prepare-inputs":
        if not 1 <= args.limit <= 1000:
            parser.error("limit must be 1..1000")
        result = prepare(args.directory, args.output, task=args.task, limit=args.limit)
    elif args.command == "run":
        result = run(args.prepared, args.protocol, args.output, system=args.system, dry_run=args.dry_run)
    elif args.command == "score":
        result = score(args.run, args.prepared, args.upstream, args.output)
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


if __name__ == "__main__":
    main()
