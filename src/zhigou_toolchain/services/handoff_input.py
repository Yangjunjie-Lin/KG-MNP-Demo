"""Meeting snapshots enter native Source/Batch/Run, never a parallel ontology store."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from zhigou_toolchain.domain_packs.registry import DomainPackRegistry
from zhigou_toolchain.ingestion.executor import execute_ingestion_plan
from zhigou_toolchain.ingestion.planner import create_ingestion_plan
from zhigou_toolchain.ingestion.source_store import SourceStore
from zhigou_toolchain.modeling.delivery.exchange_io import (
    atomic_file,
    digest,
    json_bytes,
    read_bounded,
    require,
)
from zhigou_toolchain.modeling.delivery.meeting_input import (
    generation_files,
    validate_input,
)
from zhigou_toolchain.modeling.delivery.v3 import read_zip

from .errors import ServiceBoundaryError
from .sources import load_upload, public_source


def execute(app, project, request, principal):
    try:
        path, _ = load_upload(app, project, request.parameters["upload_id"], principal)
        files = read_zip(read_bounded(path))
        parsed = validate_input(files)
        pack_ref = parsed["manifest"].get("reference_domain_pack")
        if pack_ref:
            require((pack_ref["pack_id"], pack_ref["pack_version"]) == (project.domain_pack, project.domain_pack_version), "INPUT_DOMAIN_PACK_MISMATCH")
        if "imports.lock.json" in files:
            lock = json.loads(files["imports.lock.json"])
            pack = DomainPackRegistry(app.configuration.domain_packs_root).resolve(project.domain_pack, project.domain_pack_version)
            require((lock["domain_pack"]["pack_id"], lock["domain_pack"]["pack_version"]) == (project.domain_pack, project.domain_pack_version), "INPUT_BASELINE_VERSION_MISMATCH")
            require(lock["license"]["expression"] == pack.manifest.document["license"]["expression"], "INPUT_BASELINE_LICENSE_MISMATCH")
            assets = pack.manifest.document["assets"]
            for key in ("baseline", "companion_shapes"):
                if lock.get(key):
                    require(any(digest(read_bounded(pack.root / a["path"])) == lock[key]["sha256"] for a in assets if a["kind"] in {"ontology-root", "ontology-import", "shacl-shapes"}), "INPUT_BASELINE_NOT_LOCKED_DOMAIN_ASSET")
        source_map, sources = {}, []
        store = SourceStore(project.root)
        with tempfile.TemporaryDirectory(prefix="zhigou-meeting-input-") as directory:
            for external_id, source in parsed["sources"].items():
                raw = files[source["file"]]
                local = Path(directory) / Path(source["file"]).name
                local.write_bytes(raw)
                native = store.add_file(local, source_origin="workspace-upload").source
                source_map[external_id] = native["source_id"]
                sources.append(public_source(native))
        batch = store.create_batch(source_map.values())
        plan = create_ingestion_plan(project.root, batch_id=batch["batch_id"])
        result = execute_ingestion_plan(project.root, plan.plan["plan_id"], domain_packs_root=app.configuration.domain_packs_root)
        from zhigou_toolchain.modeling.five_stage.profiling import check_input
        quality = check_input(result.dataset, result.quality_report)
        require(quality["usable"] and not quality["quarantined"], "NATIVE_INPUT_QUALITY_REVIEW_REQUIRED")
        receipt = {"format": "zhigou-meeting-input-binding/1.0.0", "input_manifest_sha256": digest(files["manifest.json"]),
            "source_id_map": source_map, "run_id": result.run["run_id"], "dataset_id": result.dataset["dataset_id"],
            "native_evidence_ids": [e["evidence_id"] for e in result.dataset["evidence_records"]],
            "external_locators": parsed["evidence"], "goal_and_rules": parsed["goal_and_rules"],
            "input_quality": parsed["quality"], "scope_approval": "NOT_GRANTED", "acceptance": "NOT_IMPORTED_USE_INDEPENDENT_SESSION_INPUT"}
        root = Path(project.root) / "artifacts/builds/handoff-input" / digest(files["manifest.json"])
        # Never retain the whole ZIP or independent answers in the Source store.
        for name, raw in {**generation_files(files), "binding.json": json_bytes(receipt)}.items():
            target = root / name
            if target.exists():
                require(read_bounded(target) == raw, "INPUT_IDEMPOTENCY_CONFLICT")
            else:
                atomic_file(target, raw)
        return {"sources": sources, "batch": batch, "plan": plan.plan, "run": result.run, "quality": result.quality_report,
                "binding": receipt, "approval": "NOT_GRANTED"}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        code = str(exc) if isinstance(exc, ValueError) and str(exc).replace("_", "").isalnum() else "MEETING_INPUT_INVALID"
        raise ServiceBoundaryError(code, "input handoff rejected; check manifest, sources, references and permissions", status_code=422) from exc
