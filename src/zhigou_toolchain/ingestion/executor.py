"""Transactional execution of validated deterministic ingestion plans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import ValidationError

from zhigou_toolchain._path_security import _is_link_like
from zhigou_toolchain.contracts.canonical import bytes_sha256, semantic_hash, stable_urn
from zhigou_toolchain.contracts.document_io import (
    atomic_write_json,
    deterministic_json_bytes,
)
from zhigou_toolchain.contracts.identifiers import resolve_within
from zhigou_toolchain.contracts.registry import validate_contract
from zhigou_toolchain.plugins.models import MediaDetectionRequest, ResourceLimits
from zhigou_toolchain.plugins.registry import PluginRegistry
from zhigou_toolchain.plugins.snapshot import verify_snapshot

from .artifact_writer import artifact_manifest, artifact_reference
from .errors import (
    ArtifactTamperedError,
    IngestionError,
    IngestionPlanError,
    QualityGateError,
)
from .evidence import build_evidence_bundle, verify_evidence_closure
from .kgir import build_dataset, build_items_for_source, validate_dataset_closure
from .models import IngestionResult
from .normalization import normalize_units
from .parser_protocol import parse_with_provider
from .planner import load_ingestion_plan, validate_plan_closure
from .quality import build_quality_report, preview_quality_report_id
from .source_store import SourceStore
from .transaction import IngestionTransaction, WorkspaceOperationLock

SCHEMA_IDS = {
    "source-asset": "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/toolchain/source-asset/1.0",
    "ingestion-plan": "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/toolchain/ingestion-plan/1.0",
    "ingestion-run": "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/toolchain/ingestion-run/1.0",
    "plugin-snapshot": "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/toolchain/plugin-snapshot/1.0",
    "evidence-record": "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/toolchain/evidence-record/1.0",
    "kg-ir-dataset": "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/toolchain/kg-ir-dataset/1.0",
    "quality-report": "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/toolchain/quality-report/1.0",
    "validation-report": "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/toolchain/validation-report/1.0",
}


def _artifact(
    *,
    artifact_type: str,
    contract: str,
    path: str,
    content: bytes,
    dependencies: tuple[str, ...] = (),
    provenance: tuple[str, ...] = (),
) -> dict[str, Any]:
    return artifact_reference(
        artifact_type=artifact_type,
        contract_name=contract,
        contract_version="1.0.0",
        schema_id=SCHEMA_IDS[contract],
        path=path,
        content=content,
        dependencies=dependencies,
        provenance_refs=provenance,
    )


def _snapshot_descriptor(registry: PluginRegistry, snapshot: dict[str, Any]):
    descriptor = registry.get(snapshot["plugin_id"])
    verify_snapshot(descriptor, snapshot)
    return descriptor


def _step(plan: dict[str, Any], source_id: str, operation: str) -> dict[str, Any]:
    matches = [item for item in plan["steps"] if item["source_id"] == source_id and item["operation"] == operation]
    if len(matches) != 1:
        raise IngestionPlanError(f"plan requires exactly one {operation} step for {source_id}")
    return matches[0]


def _snapshot(plan: dict[str, Any], snapshot_id: str) -> dict[str, Any]:
    return next(item for item in plan["plugin_snapshots"] if item["snapshot_id"] == snapshot_id)


def _formal_artifact_digests(workspace: Path) -> dict[str, str]:
    """Ingestion cannot mutate formal output, but may follow a prior release."""
    result = {}
    for relative in ("artifacts/confirmed", "artifacts/packages"):
        directory = workspace / relative
        if _is_link_like(directory):
            raise IngestionError("linked formal authority directory rejected")
        for path in sorted(directory.rglob("*")):
            if _is_link_like(path):
                raise IngestionError("linked formal artifact rejected")
            if path.is_file():
                result[path.relative_to(workspace).as_posix()] = bytes_sha256(path.read_bytes())
    return result


def execute_ingestion_plan(
    workspace: Path | str,
    plan_path_or_id: str | Path,
    *,
    enabled_plugins: tuple[str, ...] = (),
    allow_partial: bool = False,
    domain_packs_root: Path | str | None = None,
) -> IngestionResult:
    root = Path(workspace).resolve(strict=True)
    plan = load_ingestion_plan(root, plan_path_or_id)
    store = SourceStore(root, limits=ResourceLimits(**plan["resource_limits"]))
    validate_plan_closure(plan, store)
    if plan["status"] != "READY":
        raise IngestionPlanError(
            "IngestionPlan is UNRESOLVED; missing or conflicting provider requires review"
        )
    if allow_partial:
        # The flag authorizes a status, never silent partial behavior. Current core
        # still fails closed because no bounded partial strategy is needed by v1.
        pass
    snapshots = tuple(plan["plugin_snapshots"])
    run_core = {
        "project_lock_id": plan["project_lock_id"],
        "source_batch_id": plan["source_batch_id"],
        "ingestion_plan_id": plan["plan_id"],
        "plugin_snapshot_ids": sorted(item["snapshot_id"] for item in snapshots),
        "execution_profile": "KG-MNP Deterministic Ingestion Execution v1",
    }
    run_id = stable_urn("ingestion-run", run_core)
    run_hash = run_id.rsplit(":", 1)[-1]
    existing = _load_existing_run(root, run_hash)
    if existing is not None:
        return existing
    registry = PluginRegistry(allowlist=enabled_plugins)
    limits = ResourceLimits(**plan["resource_limits"])
    with WorkspaceOperationLock(root, "ingestion"):
        formal_before = _formal_artifact_digests(root)
        if any(path.startswith("artifacts/confirmed/") for path in formal_before):
            from zhigou_toolchain.workspace.security import validate_confirmed_authority
            try:
                validate_confirmed_authority(root, domain_packs_root=domain_packs_root)
            except Exception as exc:  # the single Workspace validator remains the authority
                raise IngestionError("confirmed authority is invalid; ingestion cannot legitimize it") from exc
        existing = _load_existing_run(root, run_hash)
        if existing is not None:
            return existing
        sources: dict[str, tuple[dict[str, Any], bytes]] = {}
        all_units: dict[str, tuple] = {}
        evidence_records: list[dict[str, Any]] = []
        transformations: dict[str, dict[str, Any]] = {}
        items: list[dict[str, Any]] = []
        quality_flags: set[str] = set()
        batch = store.load_batch(plan["source_batch_id"])
        for source_id in batch["sources"]:
            source = store.verify_source(source_id)
            content = store.blob_for(source).read_bytes()
            sources[source_id] = (source, content)
            detect_step = _step(plan, source_id, "detect")
            detect_snapshot = _snapshot(plan, detect_step["plugin_snapshot_id"])
            detector_descriptor = _snapshot_descriptor(registry, detect_snapshot)
            detector = registry.load(detector_descriptor.plugin_id)
            detection = detector.detect(MediaDetectionRequest(content, source["original_name"], source["declared_media_type"], limits))
            if detection.detected_media_type != source["detected_media_type"]:
                raise IngestionPlanError("media detection replay differs from SourceAsset")
            parse_step = _step(plan, source_id, "parse")
            parser_snapshot = _snapshot(plan, parse_step["plugin_snapshot_id"])
            parser_descriptor = _snapshot_descriptor(registry, parser_snapshot)
            parser = registry.load(parser_descriptor.plugin_id)
            parsed = parse_with_provider(parser, content=content, media_type=source["detected_media_type"], limits=limits)
            normalize_step = _step(plan, source_id, "normalize")
            normalizer_snapshot = _snapshot(plan, normalize_step["plugin_snapshot_id"])
            normalizer_descriptor = _snapshot_descriptor(registry, normalizer_snapshot)
            normalized = normalize_units(registry.load(normalizer_descriptor.plugin_id), parsed)
            all_units[source_id] = normalized
            for unit in normalized:
                quality_flags.update(unit.quality_flags)
            bundle = build_evidence_bundle(source=source, content=content, units=normalized, parser_snapshot_id=parser_snapshot["snapshot_id"])
            evidence_records.extend(bundle.evidence_records)
            for transformation in bundle.transformation_records:
                transformations[transformation["transformation_id"]] = transformation
        evidence_tuple = tuple(sorted(evidence_records, key=lambda item: item["evidence_id"]))
        transformation_tuple = tuple(transformations[key] for key in sorted(transformations))
        verify_evidence_closure(records=evidence_tuple, transformations=transformation_tuple, snapshots=snapshots, sources=sources, limits=limits)
        for source_id in batch["sources"]:
            source, _content = sources[source_id]
            source_evidence = tuple(item for item in evidence_tuple if item["source_id"] == source_id)
            items.extend(build_items_for_source(source=source, units=all_units[source_id], evidence_records=source_evidence))
        quality_report_id = preview_quality_report_id(run_id, tuple(sorted(quality_flags)))
        evidence_bytes = deterministic_json_bytes(list(evidence_tuple))
        snapshot_bytes = deterministic_json_bytes(list(snapshots))
        evidence_path = f"artifacts/evidence/{run_hash}/evidence-records.json"
        snapshot_path = f"artifacts/builds/ingestion/{run_hash}/plugin-snapshots.json"
        evidence_ref = _artifact(artifact_type="ingestion-evidence-set", contract="evidence-record", path=evidence_path, content=evidence_bytes)
        snapshot_ref = _artifact(artifact_type="plugin-snapshot-set", contract="plugin-snapshot", path=snapshot_path, content=snapshot_bytes)
        embedded_manifest = artifact_manifest((evidence_ref, snapshot_ref))
        dataset = build_dataset(
            project_lock_id=plan["project_lock_id"], source_batch_id=plan["source_batch_id"],
            ingestion_plan_id=plan["plan_id"], items=tuple(items),
            evidence_records=evidence_tuple, transformation_records=transformation_tuple,
            plugin_snapshots=snapshots, artifact_manifest=embedded_manifest,
            quality_report_id=quality_report_id,
        )
        quality = build_quality_report(
            subject_id=run_id, item_count=len(dataset["items"]),
            evidence_count=len(evidence_tuple), issues=tuple(sorted(quality_flags)),
        )
        if quality["quality_report_id"] != quality_report_id:
            raise IngestionError("quality report deterministic ID mismatch")
        if quality["gate_status"] == "FAIL":
            raise QualityGateError("structural quality gate failed")
        dataset_bytes = deterministic_json_bytes(dataset)
        quality_bytes = deterministic_json_bytes(quality)
        dataset_path = f"artifacts/ir/{run_hash}/kg-ir-dataset.json"
        quality_path = f"artifacts/validation/ingestion/{run_hash}/quality-report.json"
        dataset_ref = _artifact(artifact_type="kg-ir-dataset", contract="kg-ir-dataset", path=dataset_path, content=dataset_bytes, dependencies=(evidence_ref["artifact_id"],), provenance=(evidence_ref["artifact_id"],))
        quality_ref = _artifact(artifact_type="ingestion-quality-report", contract="quality-report", path=quality_path, content=quality_bytes, dependencies=(dataset_ref["artifact_id"],))
        plan_bytes = deterministic_json_bytes(plan)
        plan_formal_path = f"artifacts/builds/ingestion/{run_hash}/ingestion-plan.json"
        plan_ref = _artifact(artifact_type="ingestion-plan", contract="ingestion-plan", path=plan_formal_path, content=plan_bytes)
        source_refs = []
        for source_id in batch["sources"]:
            source = sources[source_id][0]
            content_bytes = deterministic_json_bytes(source)
            source_refs.append(_artifact(artifact_type="source-asset", contract="source-asset", path=f"sources/records/{source_id.rsplit(':', 1)[-1]}.json", content=content_bytes))
        status = "REVIEW_REQUIRED" if quality["gate_status"] == "REVIEW_REQUIRED" else "SUCCEEDED"
        run_document = {
                "manifest_kind": "KG_MNP_INGESTION_RUN",
                "schema_version": "1.0.0",
                "run_id": run_id,
                "project_lock_id": plan["project_lock_id"],
                "source_batch_id": plan["source_batch_id"],
                "ingestion_plan_id": plan["plan_id"],
                "plugin_snapshots": list(snapshots),
                "status": status,
                "input_artifacts": sorted([plan_ref, *source_refs], key=lambda item: item["artifact_id"]),
                "output_artifacts": sorted([evidence_ref, dataset_ref, quality_ref], key=lambda item: item["artifact_id"]),
                "quality_report_id": quality_report_id,
                "issues": quality["issues"],
            }
        run = {**run_document, "content_digest": semantic_hash(run_document)}
        validate_contract("ingestion-run", run)
        run_bytes = deterministic_json_bytes(run)
        run_path = f"artifacts/builds/ingestion/{run_hash}/ingestion-run.json"
        run_ref = _artifact(artifact_type="ingestion-run", contract="ingestion-run", path=run_path, content=run_bytes, dependencies=tuple(item["artifact_id"] for item in run["output_artifacts"]))
        validation = _validation_report(run_id, quality)
        validation_bytes = deterministic_json_bytes(validation)
        validation_path = f"artifacts/validation/ingestion/{run_hash}/validation-report.json"
        validation_ref = _artifact(artifact_type="ingestion-validation-report", contract="validation-report", path=validation_path, content=validation_bytes, dependencies=(quality_ref["artifact_id"],))
        manifests = {
            "build": artifact_manifest((plan_ref, snapshot_ref, run_ref), root_artifacts=(run_ref["artifact_id"],)),
            "evidence": artifact_manifest((evidence_ref,)),
            "ir": artifact_manifest((dataset_ref,), dependencies=(evidence_ref["artifact_id"],)),
            "validation": artifact_manifest((quality_ref, validation_ref), root_artifacts=(validation_ref["artifact_id"],)),
        }
        with IngestionTransaction(root, run_hash) as transaction:
            atomic_write_json(transaction.directory("build") / "ingestion-plan.json", plan)
            atomic_write_json(transaction.directory("build") / "ingestion-run.json", run)
            atomic_write_json(transaction.directory("build") / "plugin-snapshots.json", list(snapshots))
            atomic_write_json(transaction.directory("build") / "artifact-manifest.json", manifests["build"])
            atomic_write_json(transaction.directory("evidence") / "evidence-records.json", list(evidence_tuple))
            atomic_write_json(transaction.directory("evidence") / "artifact-manifest.json", manifests["evidence"])
            atomic_write_json(transaction.directory("ir") / "kg-ir-dataset.json", dataset)
            atomic_write_json(transaction.directory("ir") / "artifact-manifest.json", manifests["ir"])
            atomic_write_json(transaction.directory("validation") / "quality-report.json", quality)
            atomic_write_json(transaction.directory("validation") / "validation-report.json", validation)
            atomic_write_json(transaction.directory("validation") / "artifact-manifest.json", manifests["validation"])
            if _formal_artifact_digests(root) != formal_before:
                raise IngestionError("formal artifacts changed during ingestion; output not committed")
            transaction.commit()
        return IngestionResult(run=run, dataset=dataset, quality_report=quality)


def _validation_report(run_id: str, quality: dict[str, Any]) -> dict[str, Any]:
    warnings = sum(issue["severity"] == "WARNING" for issue in quality["issues"])
    errors = sum(issue["severity"] == "ERROR" for issue in quality["issues"])
    report = {
        "manifest_kind": "KG_MNP_VALIDATION_REPORT",
        "schema_version": "1.0.0",
        "validator": "kg-mnp-ingestion",
        "validator_version": "1.0.0",
        "subject": run_id,
        "status": "VALID" if errors == 0 else "INVALID",
        "checks": [
            {"code": "INGESTION_CLOSURE", "severity": "INFO", "path": "$", "message": "Source, Plugin, transformation, Evidence and KG-IR closure verified.", "contract_name": "ingestion-run"}
        ],
        "summary": {"error_count": errors, "warning_count": warnings, "info_count": 1},
    }
    validate_contract("validation-report", report)
    return report


def _load_existing_run(root: Path, run_hash: str) -> IngestionResult | None:
    build = root / "artifacts" / "builds" / "ingestion" / run_hash
    evidence = root / "artifacts" / "evidence" / run_hash
    ir = root / "artifacts" / "ir" / run_hash
    validation = root / "artifacts" / "validation" / "ingestion" / run_hash
    directories = (build, evidence, ir, validation)
    present = [item.exists() for item in directories]
    if not any(present):
        return None
    if not all(present):
        raise ArtifactTamperedError("partial formal ingestion run exists")
    try:
        run = json.loads((build / "ingestion-run.json").read_bytes())
        dataset = json.loads((ir / "kg-ir-dataset.json").read_bytes())
        quality = json.loads((validation / "quality-report.json").read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactTamperedError(f"cannot load existing run: {exc}") from exc
    _verify_run_document(run)
    validate_dataset_closure(dataset)
    validate_contract("quality-report", quality)
    for reference in [*run["input_artifacts"], *run["output_artifacts"]]:
        path = resolve_within(root, reference["path"])
        if bytes_sha256(path.read_bytes()) != reference["sha256"]:
            raise ArtifactTamperedError(f"artifact hash mismatch: {reference['path']}")
    for manifest_path in (
        build / "artifact-manifest.json",
        evidence / "artifact-manifest.json",
        ir / "artifact-manifest.json",
        validation / "artifact-manifest.json",
    ):
        try:
            manifest = json.loads(manifest_path.read_bytes())
            validate_contract("artifact-manifest", manifest)
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise ArtifactTamperedError(f"invalid artifact manifest: {manifest_path.name}") from exc
        expected = artifact_manifest(
            tuple(manifest["artifacts"]),
            root_artifacts=tuple(manifest["root_artifacts"]),
            dependencies=tuple(manifest["dependencies"]),
        )
        if manifest != expected:
            raise ArtifactTamperedError("artifact manifest deterministic closure mismatch")
        for reference in manifest["artifacts"]:
            artifact_path = resolve_within(root, reference["path"])
            if bytes_sha256(artifact_path.read_bytes()) != reference["sha256"]:
                raise ArtifactTamperedError(f"manifest artifact hash mismatch: {reference['path']}")
    return IngestionResult(run=run, dataset=dataset, quality_report=quality)


def inspect_run(workspace: Path | str, run_id: str) -> IngestionResult:
    digest = run_id.rsplit(":", 1)[-1]
    if len(digest) != 64:
        raise IngestionError("invalid IngestionRun ID")
    result = _load_existing_run(Path(workspace).resolve(strict=True), digest)
    if result is None:
        raise IngestionError(f"unknown IngestionRun: {run_id}")
    return result


def _verify_run_document(run: dict[str, Any]) -> None:
    validate_contract("ingestion-run", run)
    core = {
        "project_lock_id": run["project_lock_id"],
        "source_batch_id": run["source_batch_id"],
        "ingestion_plan_id": run["ingestion_plan_id"],
        "plugin_snapshot_ids": sorted(item["snapshot_id"] for item in run["plugin_snapshots"]),
        "execution_profile": "KG-MNP Deterministic Ingestion Execution v1",
    }
    if run["run_id"] != stable_urn("ingestion-run", core):
        raise ArtifactTamperedError("IngestionRun deterministic ID mismatch")
    if run["content_digest"] != semantic_hash({k: v for k, v in run.items() if k != "content_digest"}):
        raise ArtifactTamperedError("IngestionRun content digest mismatch")
