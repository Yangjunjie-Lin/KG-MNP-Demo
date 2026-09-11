"""New operations dispatched through the existing fenced modeling service."""
from __future__ import annotations

from importlib.metadata import version

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn
from zhigou_toolchain.modeling.control_plane.service import ModelingWorkspaceService
from zhigou_toolchain.modeling.five_stage.compatible import configured_client
from zhigou_toolchain.modeling.five_stage.contracts import artifact, bind_job, receipt
from zhigou_toolchain.modeling.five_stage.profiling import check_input, profile_data
from zhigou_toolchain.modeling.five_stage.tools import (
    ToolBlocked,
)

from .errors import ServiceBoundaryError
from .sources import verified_run


def execute(app, project, request, principal):
    """A real verified source run is mandatory. No client file paths or roles."""
    if request.operation_id == "modeling.tutorial.seed":
        return seed_tutorial(app, project, request, principal)
    run_id = request.parameters["run_id"]
    run = verified_run(project.root, run_id)
    session = stable_urn("modeling-session", {"project_id": project.project_id, "source_run_id": run_id})
    def make(value, step, kind="REPORT"):
        return artifact(value, project_id=project.project_id, session_id=session, step_id=step,
                        produced_by=request.operation_id, data_kind=kind)
    source = make(run.dataset, "0.0", "KG_IR")
    checked = make(check_input(run.dataset, run.quality_report), "1.1")
    receipts, artifacts = [], [source, checked]
    if request.operation_id == "modeling.profile":
        receipts.append(receipt("1.1", [source], [checked], configuration={"policy": "EVIDENCE_REQUIRED_V1"},
                                tools={"pydantic": version("pydantic")}, scope="Verified KG-IR contract/evidence and per-item quality routing; not raw document cleaning."))
        try:
            profile, versions = profile_data(run.dataset, checked["content"])
        except ImportError:
            raise ServiceBoundaryError("PROFILE_DEPENDENCY_MISSING", "Explicitly install the modeling-analysis extra", status_code=422) from None
        profiled = make(profile, "1.2")
        artifacts.append(profiled)
        receipts.append(receipt("1.2", [source, checked], [profiled], configuration={"rule_inference": "NONE"},
                                tools=versions, scope="All eligible items in selected verified run; lexical values remain strings."))
    else:
        schema = {"type": "object", "additionalProperties": False, "required": ["objects", "targets", "exclusions", "unresolved"],
                  "properties": {name: {"type": "array", "maxItems": 100, "items": {"type": "string", "maxLength": 1000}}
                                 for name in ("objects", "targets", "exclusions", "unresolved")}}
        model = None
        try:
            model = configured_client()
            profile, _ = profile_data(run.dataset, checked["content"])
            context = {"profile": profile, "business_goal": request.parameters["business_goal"],
                       "business_rules": request.parameters["business_rules"]}
            value = model.propose("Draft scope objects, acceptance targets, exclusions and unresolved ambiguities. Do not infer hard rules from samples.", context, schema)
        except (ToolBlocked, ImportError):
            raise ServiceBoundaryError("BLOCKED_BY_PROVIDER", "Configured model or analysis dependency unavailable, or model output rejected; no silent fallback was executed", status_code=422) from None
        finally:
            if model:
                model.close()
        draft = make(value, "1.3", "MODELING_CANDIDATE")
        artifacts.append(draft)
        receipts.append(receipt("1.3", [source, checked], [draft], configuration={"context_hash": semantic_hash(context)},
                                tools=value["tool_versions"], scope="Structured scope suggestion only. Identity policy still requires explicit human scope input.",
                                execution_kind="LIVE", model_revision=value["model"]["configured_revision"]))
    result = {"schema_version": "1.0.0", "session_id": session, "source_run_id": run_id,
              "artifacts": artifacts, "step_runs": bind_job(receipts, request.idempotency_key), "authority": "PROPOSAL_OR_OBSERVATION_ONLY"}
    identifier = stable_urn("five-stage-run", {"source": run_id, "operation": request.operation_id,
                            "artifacts": [a["ref"] for a in artifacts], "job_id": request.idempotency_key})
    ModelingWorkspaceService(project.root).write_build(identifier, {"five-stage-run.json": result})
    return {"five_stage": result}


def seed_tutorial(app, project, request, principal):
    """Explicit sandbox-only ingestion, using the same Source and KG-IR core."""
    import csv
    import io
    import json
    import tempfile
    from pathlib import Path

    from zhigou_toolchain.ingestion.executor import execute_ingestion_plan
    from zhigou_toolchain.ingestion.planner import create_ingestion_plan
    from zhigou_toolchain.ingestion.source_store import SourceStore
    from zhigou_toolchain.modeling.five_stage.registry import tutorial_files

    from .models import OperationRequest
    from .sources import public_source

    store = SourceStore(project.root)
    if store.list_sources():
        raise ServiceBoundaryError("SANDBOX_NOT_EMPTY", "Tutorial seeding requires a new empty project", status_code=409)
    files = tutorial_files()
    data = json.loads(files["input/records.json"])
    uploads = {}
    for key in ("employees", "departments"):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(data[key][0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(data[key])
        uploads[key + ".csv"] = stream.getvalue().encode("utf-8")
    uploads["staff_note.txt"] = json.loads(files["input/text_blocks.json"])["text"].encode("utf-8")
    sources = []
    with tempfile.TemporaryDirectory(prefix="kg-mnp-tutorial-") as directory:
        for name, content in uploads.items():
            path = Path(directory) / name
            path.write_bytes(content)
            sources.append(store.add_file(path, declared_media_type="text/csv" if name.endswith(".csv") else "text/plain",
                                          display_name=name, source_origin="workspace-upload").source)
    batch = store.create_batch([s["source_id"] for s in sources])
    plan = create_ingestion_plan(project.root, batch_id=batch["batch_id"])
    run = execute_ingestion_plan(project.root, plan.plan["plan_id"], domain_packs_root=app.configuration.domain_packs_root)
    profile = execute(app, project, OperationRequest("modeling.profile", project.project_id, {"run_id": run.run["run_id"]},
                                                    idempotency_key=request.idempotency_key), principal)
    return {**profile, "sources": [public_source(s) for s in sources], "batch": batch, "plan": plan.plan, "run": run.run,
            "quality": run.quality_report, "tutorial_origin": "SYNTHETIC_INPUT_REAL_DETERMINISTIC_EXECUTION",
            "approval": "NOT_GRANTED", "remaining": "Minimal baseline does not supply HR semantics; structure/model/review configuration is still required."}
