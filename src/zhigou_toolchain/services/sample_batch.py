"""Explicit empty-project sample loading through real ingestion cores."""
from zhigou_toolchain.domain_packs.registry import DomainPackRegistry
from zhigou_toolchain.ingestion.executor import execute_ingestion_plan
from zhigou_toolchain.ingestion.planner import create_ingestion_plan
from zhigou_toolchain.ingestion.source_store import SourceStore

from .errors import ServiceBoundaryError
from .sources import public_source


def execute(app, project, request, principal):
    pack = DomainPackRegistry(app.configuration.domain_packs_root).resolve(project.domain_pack, project.domain_pack_version)
    store = SourceStore(project.root)
    if store.list_sources():
        raise ServiceBoundaryError("SAMPLE_PROJECT_NOT_EMPTY", "Sample loading requires an empty isolated project", status_code=409)
    assets = [a for a in pack.manifest.document["assets"] if a["kind"] == "fixture" and a["media_type"] in {"text/csv", "text/plain"}]
    if not assets:
        raise ServiceBoundaryError("SAMPLE_UNSUPPORTED", "This Domain Pack has no declared CSV/text input fixtures", status_code=422)
    sources = [store.add_file(pack.root / a["path"], declared_media_type=a["media_type"], display_name=(pack.root / a["path"]).name,
                            source_origin="workspace-upload").source for a in assets]
    batch = store.create_batch([s["source_id"] for s in sources])
    plan = create_ingestion_plan(project.root, batch_id=batch["batch_id"])
    run = execute_ingestion_plan(project.root, plan.plan["plan_id"], domain_packs_root=app.configuration.domain_packs_root)
    return {"sources": [public_source(s) for s in sources], "batch": batch, "plan": plan.plan, "run": run.run,
            "quality": run.quality_report, "data_origin": "DECLARED_DOMAIN_PACK_SYNTHETIC_FIXTURES", "mode": "DETERMINISTIC", "approval": "NOT_GRANTED"}
