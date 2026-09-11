"""Deterministic core ingestion planner; no LLM or agent execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zhigou_toolchain.contracts.canonical import stable_urn
from zhigou_toolchain.contracts.catalog import ContractCatalog
from zhigou_toolchain.contracts.document_io import atomic_write_json
from zhigou_toolchain.plugins.errors import ProviderSelectionError
from zhigou_toolchain.plugins.registry import PluginRegistry
from zhigou_toolchain.plugins.selection import select_provider
from zhigou_toolchain.plugins.snapshot import build_snapshot
from zhigou_toolchain.workspace.service import open_workspace

from .contracts import finalize_document, verify_finalized_document
from .errors import IngestionPlanError
from .limits import DEFAULT_LIMITS, ResourceLimits
from .models import PlanResult
from .source_store import SourceStore


def _issue(code: str, message: str, severity: str = "ERROR") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def _step(
    *,
    source_id: str,
    operation: str,
    snapshot_id: str,
    capability: str,
    output_contract: str,
    configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    core = {
        "source_id": source_id,
        "operation": operation,
        "plugin_snapshot_id": snapshot_id,
        "required_capability": capability,
        "input_contract": "source-asset" if operation in {"detect", "parse"} else "plugin-common",
        "output_contract": output_contract,
        "configuration": configuration or {},
        "expected_outputs": [output_contract],
        "fallback_steps": [],
    }
    return {"step_id": stable_urn("ingestion-step", core), **core}


def validate_plan_closure(plan: dict[str, Any], store: SourceStore) -> None:
    verify_finalized_document(plan, contract="ingestion-plan", id_field="plan_id", urn_kind="ingestion-plan")
    batch = store.load_batch(plan["source_batch_id"])
    if batch["project_lock_id"] != plan["project_lock_id"]:
        raise IngestionPlanError("IngestionPlan ProjectLock mismatch")
    snapshot_ids = {item["snapshot_id"] for item in plan["plugin_snapshots"]}
    step_ids = {item["step_id"] for item in plan["steps"]}
    if len(step_ids) != len(plan["steps"]):
        raise IngestionPlanError("duplicate IngestionPlan step ID")
    for step in plan["steps"]:
        if step["source_id"] not in batch["sources"]:
            raise IngestionPlanError("IngestionPlan step references unknown source")
        if step["plugin_snapshot_id"] not in snapshot_ids:
            raise IngestionPlanError("IngestionPlan step references unknown PluginSnapshot")
        if any(item not in step_ids for item in step["fallback_steps"]):
            raise IngestionPlanError("IngestionPlan fallback references unknown step")
        if step["step_id"] in step["fallback_steps"]:
            raise IngestionPlanError("IngestionPlan fallback cycle")


def create_ingestion_plan(
    workspace: Path | str,
    *,
    batch_id: str,
    prefer_plugin: str | None = None,
    enabled_plugins: tuple[str, ...] = (),
    allow_nondeterministic: bool = False,
    limits: ResourceLimits = DEFAULT_LIMITS,
) -> PlanResult:
    opened = open_workspace(workspace)
    catalog = ContractCatalog.load()
    if opened.lock.document["contract_catalog_digest"] != catalog.digest:
        raise IngestionPlanError(
            "CONTRACT_CATALOG_MISMATCH: Project Lock is stale; run workspace lock"
        )
    store = SourceStore(opened.root, limits=limits)
    batch = store.load_batch(batch_id)
    registry = PluginRegistry(allowlist=enabled_plugins)
    snapshots: dict[str, dict[str, Any]] = {}
    steps: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for source_id in batch["sources"]:
        source = store.verify_source(source_id)
        media_type = source["detected_media_type"]
        try:
            detector = select_provider(
                registry.list(), plugin_kind="media-detector", capability="detect-media",
                media_type=media_type, strict_determinism=not allow_nondeterministic,
            )
            detector_snapshot = build_snapshot(detector.descriptor)
            snapshots[detector_snapshot["snapshot_id"]] = detector_snapshot
            steps.append(_step(source_id=source_id, operation="detect", snapshot_id=detector_snapshot["snapshot_id"], capability="detect-media", output_contract="source-asset"))
        except ProviderSelectionError as exc:
            issues.append(_issue("MISSING_MEDIA_DETECTOR", str(exc)))
            continue
        parser_capability = _parser_capability(media_type)
        if source["metadata"]["media_conflicts"]:
            issues.append(_issue("MEDIA_TYPE_CONFLICT", "; ".join(source["metadata"]["media_conflicts"]), "WARNING"))
        if parser_capability is None:
            code = "MISSING_TRANSCRIPTION_OR_VIDEO_PROVIDER" if media_type.startswith(("video/", "audio/")) else "MISSING_PROVIDER"
            issues.append(_issue(code, f"no honest Prompt 3 semantic parser for {media_type}", "WARNING"))
            continue
        try:
            parser_selection = select_provider(
                registry.list(), plugin_kind="parser", capability=parser_capability,
                media_type=media_type, preference=prefer_plugin,
                strict_determinism=not allow_nondeterministic,
            )
            parser_snapshot = build_snapshot(parser_selection.descriptor)
            snapshots[parser_snapshot["snapshot_id"]] = parser_snapshot
            steps.append(_step(source_id=source_id, operation="parse", snapshot_id=parser_snapshot["snapshot_id"], capability=parser_capability, output_contract="plugin-common", configuration={"selection_reason": parser_selection.reason}))
            normalizer_selection = select_provider(
                registry.list(), plugin_kind="normalizer", capability="normalize-generic",
                media_type=media_type, strict_determinism=not allow_nondeterministic,
            )
            normalizer_snapshot = build_snapshot(normalizer_selection.descriptor)
            snapshots[normalizer_snapshot["snapshot_id"]] = normalizer_snapshot
            steps.append(_step(source_id=source_id, operation="normalize", snapshot_id=normalizer_snapshot["snapshot_id"], capability="normalize-generic", output_contract="transformation-record"))
            quality_selection = select_provider(
                registry.list(), plugin_kind="quality-evaluator", capability="evaluate-structural-quality",
                media_type=media_type, strict_determinism=not allow_nondeterministic,
            )
            quality_snapshot = build_snapshot(quality_selection.descriptor)
            snapshots[quality_snapshot["snapshot_id"]] = quality_snapshot
            steps.append(_step(source_id=source_id, operation="quality-evaluate", snapshot_id=quality_snapshot["snapshot_id"], capability="evaluate-structural-quality", output_contract="quality-report"))
        except ProviderSelectionError as exc:
            issues.append(_issue("MISSING_PROVIDER", str(exc), "WARNING"))
    status = "READY" if not issues else "UNRESOLVED"
    plan = finalize_document(
        {
            "manifest_kind": "KG_MNP_INGESTION_PLAN",
            "schema_version": "1.0.0",
            "project_id": opened.manifest.project_id,
            "project_lock_id": opened.lock.lock_id,
            "source_batch_id": batch_id,
            "planner": {"planner_id": "kg-mnp-deterministic-core", "planner_version": "1.0.0", "planner_kind": "DETERMINISTIC_CORE"},
            "plugin_snapshots": sorted(snapshots.values(), key=lambda item: (item["plugin_id"], item["plugin_version"])),
            "steps": steps,
            "resource_limits": limits.to_dict(),
            "normalization_policy": {"policy_id": "basic-representation-only", "settings": {"unicode": "NFC", "newlines": "LF"}},
            "quality_policy": {"policy_id": "structural-evidence-closure", "settings": {"ground_truth": False}},
            "fallback_policy": {"policy_id": "bounded-no-retry", "settings": {"max_attempts": 1}},
            "status": status,
            "issues": sorted(issues, key=lambda item: (item["code"], item["message"])),
        },
        contract="ingestion-plan",
        id_field="plan_id",
        urn_kind="ingestion-plan",
    )
    validate_plan_closure(plan, store)
    path = opened.root / "artifacts" / "builds" / "ingestion" / "plans" / f"{plan['plan_id'].rsplit(':', 1)[-1]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_bytes())
        if existing != plan:
            raise IngestionPlanError("existing deterministic IngestionPlan differs")
    else:
        atomic_write_json(path, plan)
    return PlanResult(plan=plan, path=path)


def load_ingestion_plan(workspace: Path | str, plan_path_or_id: str | Path) -> dict[str, Any]:
    root = Path(workspace).resolve(strict=True)
    candidate = Path(plan_path_or_id)
    if candidate.exists():
        path = candidate.resolve(strict=True)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise IngestionPlanError("external IngestionPlan path rejected") from exc
    else:
        identifier = str(plan_path_or_id)
        digest = identifier.rsplit(":", 1)[-1]
        if len(digest) != 64:
            raise IngestionPlanError("invalid IngestionPlan ID")
        path = root / "artifacts" / "builds" / "ingestion" / "plans" / f"{digest}.json"
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IngestionPlanError(f"cannot load IngestionPlan: {exc}") from exc
    SourceStore(root).load_batch(value["source_batch_id"])
    validate_plan_closure(value, SourceStore(root))
    return value


def _parser_capability(media_type: str) -> str | None:
    return {
        "text/plain": "parse-text", "text/markdown": "parse-markdown",
        "application/json": "parse-json", "text/csv": "parse-delimited",
        "text/tab-separated-values": "parse-delimited",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "parse-xlsx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "parse-docx",
        "application/pdf": "parse-pdf", "image/png": "parse-image-metadata",
        "image/jpeg": "parse-image-metadata", "image/gif": "parse-image-metadata",
        "image/tiff": "parse-image-metadata", "audio/wav": "parse-wav-metadata",
    }.get(media_type)
