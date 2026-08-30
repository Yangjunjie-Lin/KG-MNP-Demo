"""Public `source`, `ingest`, and `ir` CLI routes."""

from __future__ import annotations

import argparse
import json
import traceback
from dataclasses import replace
from pathlib import Path

from jsonschema import ValidationError

from kg_mnp.contracts.cli import command_result, emit_json
from kg_mnp.plugins.errors import PluginError

from .errors import (
    ArtifactTamperedError,
    IngestionError,
    IngestionPlanError,
    SourceError,
)
from .executor import execute_ingestion_plan, inspect_run
from .kgir import validate_dataset_closure
from .limits import DEFAULT_LIMITS
from .planner import create_ingestion_plan
from .source_store import SourceStore

SUCCESS = 0
SOURCE_INVALID = 11
INGESTION_PLAN_INVALID = 12
INGESTION_FAILED = 13
QUALITY_GATE_REVIEW_REQUIRED = 14
QUALITY_GATE_FAILED = 15
ARTIFACT_TAMPERED = 16


def _source_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-mnp source")
    parser.add_argument("--debug", action="store_true")
    commands = parser.add_subparsers(dest="operation", required=True)
    add = commands.add_parser("add")
    add.add_argument("workspace", type=Path)
    add.add_argument("source", type=Path)
    add.add_argument("--recursive", action="store_true")
    add.add_argument("--domain-packs-root", type=Path)
    add.add_argument("--declared-media-type")
    add.add_argument("--max-source-bytes", type=int, default=DEFAULT_LIMITS.max_source_bytes)
    add.add_argument("--json", action="store_true")
    listing = commands.add_parser("list")
    listing.add_argument("workspace", type=Path)
    listing.add_argument("--json", action="store_true")
    for name in ("inspect", "verify"):
        command = commands.add_parser(name)
        command.add_argument("workspace", type=Path)
        command.add_argument("source_id")
        command.add_argument("--json", action="store_true")
    batch = commands.add_parser("batch-create")
    batch.add_argument("workspace", type=Path)
    batch.add_argument("source_ids", nargs="+")
    batch.add_argument("--label", action="append", default=[])
    batch.add_argument("--json", action="store_true")
    inspect_batch = commands.add_parser("batch-inspect")
    inspect_batch.add_argument("workspace", type=Path)
    inspect_batch.add_argument("batch_id")
    inspect_batch.add_argument("--json", action="store_true")
    return parser


def source_main(argv: list[str] | None = None) -> int:
    parser = _source_parser()
    arguments = parser.parse_args(argv)
    command = f"source {arguments.operation}"
    use_json = bool(getattr(arguments, "json", False))
    try:
        limits = replace(DEFAULT_LIMITS, max_source_bytes=getattr(arguments, "max_source_bytes", DEFAULT_LIMITS.max_source_bytes))
        store = SourceStore(arguments.workspace, limits=limits)
        if arguments.operation == "add":
            if arguments.source.is_dir():
                added = store.add_directory(arguments.source, recursive=arguments.recursive, declared_media_type=arguments.declared_media_type)
                result = [{"source": item.source, "duplicate": item.duplicate} for item in added]
            else:
                item = store.add_file(arguments.source, declared_media_type=arguments.declared_media_type)
                result = {"source": item.source, "duplicate": item.duplicate}
            subject = arguments.source.name
        elif arguments.operation == "list":
            result = list(store.list_sources())
            subject = "source-store"
        elif arguments.operation == "inspect":
            result = store.load_source(arguments.source_id)
            subject = arguments.source_id
        elif arguments.operation == "verify":
            result = {"source": store.verify_source(arguments.source_id), "valid": True}
            subject = arguments.source_id
        elif arguments.operation == "batch-create":
            result = store.create_batch(arguments.source_ids, labels=arguments.label)
            subject = result["batch_id"]
        else:
            result = store.load_batch(arguments.batch_id)
            subject = arguments.batch_id
        payload = command_result(command, status="SUCCESS", code=SUCCESS, subject=subject, result=result)
        if use_json:
            emit_json(payload)
        else:
            emit_json(result)
        return SUCCESS
    except (SourceError, IngestionError, ValueError) as exc:
        if arguments.debug:
            traceback.print_exc()
        payload = command_result(command, status="ERROR", code=SOURCE_INVALID, subject=getattr(arguments, "source_id", "source"), errors=[{"code": "SOURCE_INVALID", "message": str(exc)}])
        if use_json:
            emit_json(payload)
        else:
            print(f"ERROR {exc}")
        return SOURCE_INVALID


def _ingest_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-mnp ingest")
    parser.add_argument("--debug", action="store_true")
    commands = parser.add_subparsers(dest="operation", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("workspace", type=Path)
    choice = plan.add_mutually_exclusive_group(required=True)
    choice.add_argument("--batch")
    choice.add_argument("--source")
    plan.add_argument("--plugin", action="append", default=[])
    plan.add_argument("--prefer-plugin")
    plan.add_argument("--allow-nondeterministic", action="store_true")
    plan.add_argument("--json", action="store_true")
    run = commands.add_parser("run")
    run.add_argument("workspace", type=Path)
    choice = run.add_mutually_exclusive_group(required=True)
    choice.add_argument("--plan")
    choice.add_argument("--batch")
    run.add_argument("--plugin", action="append", default=[])
    run.add_argument("--prefer-plugin")
    run.add_argument("--allow-partial", action="store_true")
    run.add_argument("--allow-nondeterministic", action="store_true")
    run.add_argument("--max-attempts", type=int, default=1)
    run.add_argument("--json", action="store_true")
    for name in ("inspect", "validate", "status", "retry-plan"):
        command = commands.add_parser(name)
        command.add_argument("workspace", type=Path)
        command.add_argument("run_id")
        command.add_argument("--prefer-plugin")
        command.add_argument("--json", action="store_true")
    return parser


def ingest_main(argv: list[str] | None = None) -> int:
    parser = _ingest_parser()
    arguments = parser.parse_args(argv)
    command = f"ingest {arguments.operation}"
    use_json = bool(getattr(arguments, "json", False))
    try:
        if getattr(arguments, "max_attempts", 1) != 1:
            raise IngestionPlanError("Prompt 3 deterministic core permits max-attempts=1")
        if arguments.operation == "plan":
            batch_id = arguments.batch
            if batch_id is None:
                batch_id = SourceStore(arguments.workspace).create_batch([arguments.source])["batch_id"]
            planned = create_ingestion_plan(arguments.workspace, batch_id=batch_id, prefer_plugin=arguments.prefer_plugin, enabled_plugins=tuple(arguments.plugin), allow_nondeterministic=arguments.allow_nondeterministic)
            result = planned.plan
            code = SUCCESS if result["status"] == "READY" else INGESTION_PLAN_INVALID
            status = result["status"]
            subject = result["plan_id"]
        elif arguments.operation == "run":
            plan_id = arguments.plan
            if plan_id is None:
                planned = create_ingestion_plan(arguments.workspace, batch_id=arguments.batch, prefer_plugin=arguments.prefer_plugin, enabled_plugins=tuple(arguments.plugin), allow_nondeterministic=arguments.allow_nondeterministic)
                plan_id = planned.plan["plan_id"]
            executed = execute_ingestion_plan(arguments.workspace, plan_id, enabled_plugins=tuple(arguments.plugin), allow_partial=arguments.allow_partial)
            result = {"run": executed.run, "quality_report": executed.quality_report, "dataset_id": executed.dataset["dataset_id"]}
            code = QUALITY_GATE_REVIEW_REQUIRED if executed.run["status"] == "REVIEW_REQUIRED" else SUCCESS
            status = executed.run["status"]
            subject = executed.run["run_id"]
        elif arguments.operation == "retry-plan":
            previous = inspect_run(arguments.workspace, arguments.run_id)
            planned = create_ingestion_plan(arguments.workspace, batch_id=previous.run["source_batch_id"], prefer_plugin=arguments.prefer_plugin)
            result = {"plan": planned.plan, "previous_plan_id": previous.run["ingestion_plan_id"], "changed": planned.plan["plan_id"] != previous.run["ingestion_plan_id"]}
            code, status, subject = SUCCESS, "SUCCESS", planned.plan["plan_id"]
        else:
            executed = inspect_run(arguments.workspace, arguments.run_id)
            if arguments.operation == "inspect":
                result = {"run": executed.run, "quality_report": executed.quality_report, "dataset": executed.dataset}
            elif arguments.operation == "validate":
                validate_dataset_closure(executed.dataset)
                result = {"valid": True, "run_id": executed.run["run_id"]}
            else:
                result = {"run_id": executed.run["run_id"], "status": executed.run["status"], "quality_gate": executed.quality_report["gate_status"]}
            code, status, subject = SUCCESS, "SUCCESS", executed.run["run_id"]
        payload = command_result(command, status=status, code=code, subject=subject, result=result)
        if use_json:
            emit_json(payload)
        else:
            emit_json(result)
        return code
    except ArtifactTamperedError as exc:
        return _ingest_error(arguments, command, use_json, ARTIFACT_TAMPERED, "ARTIFACT_TAMPERED", exc)
    except IngestionPlanError as exc:
        return _ingest_error(arguments, command, use_json, INGESTION_PLAN_INVALID, "INGESTION_PLAN_INVALID", exc)
    except IngestionError as exc:
        return _ingest_error(arguments, command, use_json, INGESTION_FAILED, "INGESTION_FAILED", exc)
    except (ValidationError, PluginError, OSError, TypeError, ValueError) as exc:
        return _ingest_error(arguments, command, use_json, INGESTION_FAILED, "INGESTION_FAILED", exc)


def _ingest_error(arguments, command: str, use_json: bool, code: int, label: str, exc: Exception) -> int:
    if arguments.debug:
        traceback.print_exc()
    payload = command_result(command, status="ERROR", code=code, subject=getattr(arguments, "run_id", "ingestion"), errors=[{"code": label, "message": str(exc)}])
    if use_json:
        emit_json(payload)
    else:
        print(f"ERROR {exc}")
    return code


def _ir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kg-mnp ir")
    parser.add_argument("--debug", action="store_true")
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("inspect", "validate", "sources"):
        command = commands.add_parser(name)
        command.add_argument("workspace", type=Path)
        command.add_argument("dataset_id")
        command.add_argument("--json", action="store_true")
    trace = commands.add_parser("trace")
    trace.add_argument("workspace", type=Path)
    trace.add_argument("item_id")
    trace.add_argument("--json", action="store_true")
    return parser


def _datasets(workspace: Path) -> tuple[dict, ...]:
    result = []
    for path in sorted((workspace / "artifacts" / "ir").glob("*/kg-ir-dataset.json")):
        result.append(json.loads(path.read_bytes()))
    return tuple(result)


def ir_main(argv: list[str] | None = None) -> int:
    arguments = _ir_parser().parse_args(argv)
    command = f"ir {arguments.operation}"
    use_json = bool(getattr(arguments, "json", False))
    try:
        workspace = arguments.workspace.resolve(strict=True)
        datasets = _datasets(workspace)
        if arguments.operation == "trace":
            dataset = next(item for item in datasets if any(node["item_id"] == arguments.item_id for node in item["items"]))
            node = next(node for node in dataset["items"] if node["item_id"] == arguments.item_id)
            evidence = [item for item in dataset["evidence_records"] if item["evidence_id"] in node["evidence_refs"]]
            sources = SourceStore(workspace)
            result = {
                "kg_ir_item": node,
                "evidence_records": evidence,
                "source_locators": [item["locator"] for item in evidence],
                "source_assets": [sources.load_source(item["source_id"]) for item in evidence],
                "source_blob_hashes": sorted({item["source_content_sha256"] for item in evidence}),
                "plugin_snapshots": [item for item in dataset["plugin_snapshots"] if item["snapshot_id"] in {record["plugin_snapshot_id"] for record in evidence}],
                "transformation_records": [item for item in dataset["transformation_records"] if item["transformation_id"] in set(node["transformation_refs"])],
            }
            subject = arguments.item_id
        else:
            dataset = next(item for item in datasets if item["dataset_id"] == arguments.dataset_id)
            subject = arguments.dataset_id
            if arguments.operation == "inspect":
                result = dataset
            elif arguments.operation == "validate":
                validate_dataset_closure(dataset)
                result = {"valid": True, "dataset_id": dataset["dataset_id"]}
            else:
                result = sorted({source_id for item in dataset["items"] for source_id in item["source_ids"]})
        payload = command_result(command, status="SUCCESS", code=SUCCESS, subject=subject, result=result)
        if use_json:
            emit_json(payload)
        else:
            emit_json(result)
        return SUCCESS
    except (StopIteration, OSError, json.JSONDecodeError, IngestionError, SourceError) as exc:
        if arguments.debug:
            traceback.print_exc()
        payload = command_result(command, status="ERROR", code=INGESTION_FAILED, subject=getattr(arguments, "dataset_id", getattr(arguments, "item_id", "ir")), errors=[{"code": "KG_IR_INVALID", "message": str(exc) or "not found"}])
        if use_json:
            emit_json(payload)
        else:
            print(f"ERROR {exc or 'not found'}")
        return INGESTION_FAILED
