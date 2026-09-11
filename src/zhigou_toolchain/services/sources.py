"""Project-scoped Source and ingestion adapters; paths never come from clients."""
from __future__ import annotations

import json
import re
from pathlib import Path

from zhigou_toolchain.ingestion.errors import (
    ArtifactTamperedError,
    IngestionError,
    IngestionPlanError,
    SourceTamperedError,
)
from zhigou_toolchain.ingestion.evidence import verify_evidence_closure
from zhigou_toolchain.ingestion.executor import execute_ingestion_plan, inspect_run
from zhigou_toolchain.ingestion.limits import DEFAULT_LIMITS
from zhigou_toolchain.ingestion.planner import create_ingestion_plan
from zhigou_toolchain.ingestion.source_store import SourceStore

from .errors import ServiceBoundaryError


def public_source(source):
    return {key: value for key, value in source.items() if key not in {"blob_path", "safe_display_path"}}


def upload_root(service, project_id):
    digest = project_id.rsplit(":", 1)[-1]
    if not re.fullmatch("[a-f0-9]{64}", digest):
        raise ServiceBoundaryError("PROJECT_INVALID", "invalid project identifier", status_code=422)
    return service.root / "projects" / digest / "tmp" / "uploads"


def load_upload(service, project, upload_id, principal):
    if not re.fullmatch("[a-f0-9]{64}", upload_id):
        raise ServiceBoundaryError("UPLOAD_INVALID", "invalid upload identifier", status_code=422)
    root = upload_root(service, project.project_id)
    path = root / (upload_id + ".blob")
    from zhigou_toolchain.contracts.canonical import bytes_sha256
    try:
        record = json.loads((root / (upload_id + ".json")).read_bytes())
        if (record["project_id"] != project.project_id or record["principal_id"] != principal.principal_id
                or path.is_symlink() or bytes_sha256(path.read_bytes()) != record["sha256"]):
            raise ValueError("upload identity mismatch")
    except (OSError, ValueError, KeyError) as exc:
        raise ServiceBoundaryError("UPLOAD_INVALID", "upload unavailable or integrity check failed", status_code=409) from exc
    return path, record


def verified_run(root, run_id):
    result = inspect_run(root, run_id)
    store = SourceStore(root)
    batch = store.load_batch(result.run["source_batch_id"])
    sources = {}
    for source_id in batch["sources"]:
        source = store.verify_source(source_id)
        sources[source_id] = (source, store.blob_for(source).read_bytes())
    dataset = result.dataset
    verify_evidence_closure(records=tuple(dataset["evidence_records"]),
                            transformations=tuple(dataset["transformation_records"]),
                            snapshots=tuple(dataset["plugin_snapshots"]), sources=sources, limits=DEFAULT_LIMITS)
    return result


def execute(service, project, request, principal):
    root, params, name = Path(project.root), request.parameters, request.operation_id
    try:
        if name == "source.register":
            path, record = load_upload(service, project, params["upload_id"], principal)
            store = SourceStore(root)
            source = store.add_file(path, declared_media_type=record["media_type"],
                                    display_name=record["filename"], source_origin="workspace-upload").source
            batch = store.create_batch([source["source_id"]])
            return {"source": public_source(source), "batch": batch}
        if name in {"source.inspect", "source.verify"}:
            return {"source": public_source(SourceStore(root).verify_source(params["source_id"]))}
        if name=="source.batch":return {"batch":SourceStore(root).create_batch(params["source_ids"])}
        if name == "source.list":
            store = SourceStore(root)
            return {"sources": [public_source(store.verify_source(row["source_id"])) for row in store.list_sources()]}
        if name == "ingestion.plan":
            return {"plan": create_ingestion_plan(root, batch_id=params["batch_id"]).plan}
        if name == "ingestion.run":
            result = execute_ingestion_plan(root, params["plan_id"], domain_packs_root=service.configuration.domain_packs_root)
            return {"run": result.run, "dataset_id": result.dataset["dataset_id"], "quality": result.quality_report}
        result = verified_run(root, params["run_id"])
        if name in {"ingestion.inspect", "kgir.inspect", "kgir.validate"}:
            return {"run": result.run, "dataset": result.dataset, "quality": result.quality_report}
        if name in {"ingestion.trace", "evidence.list"}:
            records = result.dataset["evidence_records"]
            if params.get("item_id"):
                item = next((item for item in result.dataset["items"] if item["item_id"] == params["item_id"]), None)
                if item is None:
                    raise ServiceBoundaryError("ARTIFACT_NOT_FOUND", "KG-IR item not found", status_code=404)
                records = [record for record in records if record["evidence_id"] in item["evidence_refs"]]
            return {"evidence": records, "transformations": result.dataset["transformation_records"],
                    "run_id": result.run["run_id"]}
        raise ServiceBoundaryError("OPERATION_NOT_FOUND", "unknown source operation", status_code=404)
    except (ArtifactTamperedError, SourceTamperedError) as exc:
        raise ServiceBoundaryError("ARTIFACT_INTEGRITY_FAILED", "artifact or source integrity failed", status_code=409) from exc
    except IngestionPlanError as exc:
        raise ServiceBoundaryError("INGESTION_PLAN_BLOCKED", "ingestion plan invalid or provider unresolved", status_code=422) from exc
    except IngestionError as exc:
        raise ServiceBoundaryError("INGESTION_FAILED", "ingestion input or artifact is invalid", status_code=422) from exc


OPERATIONS = frozenset({"source.register", "source.inspect", "source.list", "source.verify", "source.batch", "ingestion.plan",
                        "ingestion.run", "ingestion.inspect", "ingestion.trace", "evidence.list", "kgir.inspect", "kgir.validate"})
