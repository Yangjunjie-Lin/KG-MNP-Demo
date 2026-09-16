"""Handoff operations inside the existing authorization/Worker/CAS boundary."""
from __future__ import annotations

import json
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.contracts.document_io import read_document
from zhigou_toolchain.domain_packs.registry import DomainPackRegistry
from zhigou_toolchain.ingestion.source_store import SourceStore
from zhigou_toolchain.modeling.control_plane.service import ModelingWorkspaceService
from zhigou_toolchain.modeling.delivery.exchange_io import (
    atomic_file,
    digest,
    read_bounded,
    require,
)
from zhigou_toolchain.modeling.delivery.handoff import handoff_bytes, handoff_files
from zhigou_toolchain.semantic_kernel.compiler import SemanticCompiler
from zhigou_toolchain.semantic_kernel.packaging.archive import (
    archive_mapping_bytes,
    read_verified_package_files,
)

from .compilation import package_location
from .errors import ServiceBoundaryError
from .modeling_sessions import current, read
from .sources import verified_run

OPERATIONS = frozenset({"modeling.handoff.import", "modeling.handoff.export", "modeling.evolution.export", "modeling.evolution.review"})


def execution_mode(assistance, invocations):
    """A recorded provider without LIVE assistance is still RECORDED, not deterministic."""
    modes = {r.get("execution_source") for r in assistance.get("calls", [])}
    modes.add(assistance.get("execution_source"))
    if "LIVE" in modes:
        return "LIVE"
    if "RECORDED" in modes or any(r.get("provider_type") == "RECORDED_EXTERNAL_MODEL" for r in invocations):
        return "RECORDED"
    return "DETERMINISTIC"


def build_handoff(project, *, package_id, expected_revision, source_grants, recipient,
                  data_classification, domain_packs_root=None, reasoner_jar=None, review_nature="AUTHENTICATED_HUMAN", run_observations=()):
    session = read(project.root)
    if session is None or session["revision"] != expected_revision:
        raise ValueError("HANDOFF_SESSION_REVISION_STALE")
    built = current(session, "compile.build")
    require(built and built["identifier"] == package_id, "HANDOFF_PACKAGE_STALE")
    files, _ = read_verified_package_files(package_location(project, package_id), expected_package_id=package_id)
    confirmed = json.loads(files["source/confirmed-modeling-package.json"])
    native_plan = json.loads(files["source/semantic-compilation-plan.json"])
    reviewed = current(session, "review.finalize")
    planned = current(session, "compile.plan.exact")
    require(reviewed and reviewed["identifier"] == confirmed["package_id"], "HANDOFF_REVIEW_STALE")
    require(planned and planned["identifier"] == native_plan["plan_id"], "HANDOFF_PLAN_STALE")
    compiler = SemanticCompiler(project.root, domain_packs_root=DomainPackRegistry(domain_packs_root).root, reasoner_jar=reasoner_jar)
    original_attestation = json.loads(files["source/compiler-input-attestation.json"])
    current_attestation = compiler.attest(confirmed["package_id"])
    # The native resolver picks a lexical location among byte-identical copies.
    # Compilation adds such copies to the package; that is not a changed authority.
    # Re-run all original attestation checks, then compare every ID/content/byte
    # digest, allowing only this location crosswalk. Never rewrite native hashes.
    def authority_projection(attestation):
        return {**{k: v for k, v in attestation.items() if k not in {"attestation_id", "content_digest", "resolved_artifacts"}},
                "resolved_artifacts": [{k: v for k, v in row.items() if k != "path"} for row in attestation["resolved_artifacts"]]}
    require(authority_projection(current_attestation) == authority_projection(original_attestation), "HANDOFF_AUTHORITY_STALE")
    modeling = ModelingWorkspaceService(project.root)
    resolver = compiler._resolver()
    scope = resolver.resolve(confirmed["scope_id"]).document
    scope_binding = read_document(modeling.build_directory(scope["scope_id"]) / "ingestion-binding.json")
    require(scope_binding["run_id"] == session["frozen"]["run_id"], "HANDOFF_INPUT_RUN_MISMATCH")
    run = verified_run(project.root, scope_binding["run_id"])
    require(semantic_hash(run.dataset) == session["frozen"]["dataset_digest"], "HANDOFF_INPUT_DIGEST_CHANGED")
    proposal = resolver.resolve(confirmed["source_proposal_id"]).document
    proposal_dir = modeling.proposal_directory(proposal["proposal_id"])
    store = SourceStore(project.root)
    batch = store.load_batch(run.run["source_batch_id"])
    grants = {g["source_id"]: g for g in source_grants}
    require(len(grants) == len(source_grants) and set(grants) == set(batch["sources"]), "SOURCE_EXPORT_GRANTS_REQUIRED")
    sources, dependencies = [], {}
    for source_id in batch["sources"]:
        source = store.verify_source(source_id)
        raw = read_bounded(store.blob_for(source))
        grant = grants[source_id]
        require(grant["sha256"] == digest(raw) and grant["license"] and grant["permission_basis"], "SOURCE_EXPORT_GRANT_MISMATCH")
        name = "sources/" + digest(raw) + ".blob"
        dependencies[name] = raw
        sources.append({**{k: v for k, v in source.items() if k not in {"blob_path", "safe_display_path"}}, "delivery_path": name, "native_document": source})
    records = read_document(proposal_dir / "record-mapping-proposal.json")
    extraction = read_document(proposal_dir / "source-extraction-report.json")
    responses = read_document(proposal_dir / "provider-responses.json")
    assistance_path = proposal_dir / "live-model-assistance.json"
    assistance = read_document(assistance_path) if assistance_path.exists() else {}
    mode = execution_mode(assistance, read_document(proposal_dir / "model-invocation-records.json"))
    bindings = {"project_id": project.project_id, "session_id": session["session_id"], "session_revision": session["revision"],
        "input_run_id": run.run["run_id"], "input_run": run.run, "source_batch": batch, "dataset": run.dataset,
        "sources": sources, "source_grants": source_grants, "recipient": recipient, "permission_verification": "AUTHENTICATED_EXPORTER_DECLARATION_NOT_LEGAL_ATTESTATION",
        "quality": run.quality_report, "scope": scope, "scope_approval": resolver.resolve(confirmed["scope_approval_id"]).document,
        "business_rules": session["frozen"]["business_rules"], "configuration": session["frozen"]["configuration"],
        "proposal": proposal, "package_id": package_id, "confirmed_package_id": confirmed["package_id"],
        "compilation_plan_id": native_plan["plan_id"], "compiler_snapshot_id": native_plan["compiler_snapshot_id"],
        "authority_location_crosswalk": [{"artifact_id": a["artifact_id"], "native_path": a["path"], "current_path": b["path"], "byte_sha256": a["byte_sha256"]}
            for a, b in zip(original_attestation["resolved_artifacts"], current_attestation["resolved_artifacts"], strict=True) if a["path"] != b["path"]],
        "independent_acceptance": session["frozen"]["acceptance"], "data_classification": data_classification,
        "execution_mode": mode, "review_nature": review_nature,
        "agent_runs": list(run_observations),
        "mapping_execution": {"status": "CANDIDATES_GENERATED", "record_mapping": records, "source_extraction": extraction,
                              "provider_responses": responses, "proposal_digest": proposal["content_digest"]}}
    return handoff_files(archive_mapping_bytes(files), files, bindings, dependencies)


def execute(app, project, request, principal):
    if request.operation_id == "modeling.handoff.import":
        from .handoff_input import execute as import_input
        return import_input(app, project, request, principal)
    try:
        if request.operation_id == "modeling.handoff.export":
            from .projects import load_catalog
            session = read(project.root)
            observations = []
            for job_id, receipt in load_catalog(app.root).get("commits", {}).items():
                audit = receipt["result"].get("agent_execution")
                if receipt["context"]["project_id"] == project.project_id and audit and session and audit["session_id"] == session["session_id"]:
                    observations.append({"job_id": job_id, "operation_id": receipt["context"]["operation_id"],
                        "authority_revision": receipt["authority_revision"], "result_digest": semantic_hash(receipt["result"]),
                        "native_agent_run_id": audit["run_id"], "session_id": audit["session_id"], "parent_version": audit["records"][0]["parent_version"] if audit["records"] else None})
            files = build_handoff(project, **request.parameters,
                domain_packs_root=app.configuration.domain_packs_root, reasoner_jar=app.configuration.reasoner_jar,
                run_observations=sorted(observations, key=lambda r: r["authority_revision"]),
                review_nature="SYNTHETIC_ENGINEERING" if app.configuration.review_profile == "DEVELOPMENT_SINGLE_REVIEWER" else "AUTHENTICATED_HUMAN")
            raw = handoff_bytes(files)
            result = {"status": "EXPORTED", "format": "zhigou-ontology-handoff/1.0.0", "package_id": request.parameters["package_id"],
                      "receiver_status": "NOT_CONTACTED", "release_status": "NOT_GRANTED_BY_EXPORT"}
        else:
            from .ontology_traces import export_trace, submit_review
            if request.operation_id == "modeling.evolution.review":
                return submit_review(app, project, request, principal)
            files, result = export_trace(app, project, request, principal)
            raw = archive_mapping_bytes(files)
        artifact_id = digest(raw)
        path = Path(project.root) / "artifacts" / "builds" / "handoff" / (artifact_id + ".zip")
        if path.exists():
            require(read_bounded(path) == raw, "HANDOFF_OUTPUT_CONFLICT")
        else:
            atomic_file(path, raw)
        return {**result, "sha256": artifact_id, "size_bytes": len(raw),
                **({"source_job_id": request.parameters["job_id"]} if request.operation_id == "modeling.evolution.export" else {})}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Only our enumerated error labels, never a path or arbitrary provider text.
        code = str(exc) if isinstance(exc, ValueError) and str(exc).replace("_", "").isalnum() else "HANDOFF_INPUT_OR_PROTOCOL_INVALID"
        raise ServiceBoundaryError(code, "handoff binding, authority or protocol validation failed", status_code=409) from exc


def download(app, principal, project_id, job_id):
    from .authorization_policy import authorize
    from .execution import committed_result
    from .models import OperationRequest
    from .projects import get_project, load_catalog, require_access
    def check():
        actor = app._current(principal)
        job = app._job(job_id, actor)
        require_access(actor, get_project(app.root, project_id))
        if job.project_id != project_id or job.operation_id not in {"modeling.handoff.export", "modeling.evolution.export"}:
            raise ServiceBoundaryError("EXPORT_SCOPE_INVALID", "export task belongs to another resource", status_code=404)
        authorize(actor, app.catalog[job.operation_id], OperationRequest(job.operation_id, project_id))
        return job
    job = check()
    result = committed_result(app, job)
    if result is None:
        raise ServiceBoundaryError("EXPORT_NOT_READY", "export has no verified commit", status_code=409)
    generation = Path(load_catalog(app.root)["commits"][job_id]["root"])
    raw = read_bounded(generation / "artifacts/builds/handoff" / (result["sha256"] + ".zip"))
    require(digest(raw) == result["sha256"] and len(raw) == result["size_bytes"], "EXPORT_BYTES_CHANGED")
    check()
    return raw
