"""Private trace journal and authenticated export, never a second job authority."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.delivery.evolution import (
    evolution_files,
    validate_review,
)
from zhigou_toolchain.modeling.delivery.exchange_io import (
    atomic_file,
    digest,
    json_bytes,
    read_bounded,
    require,
)
from zhigou_toolchain.modeling.delivery.trace import (
    TraceRecorder,
    freeze_harness,
    public_value,
)
from zhigou_toolchain.ontology_io.provenance import runtime_versions, source_identity
from zhigou_toolchain.workspace.locking import load_project_lock

from .errors import ServiceBoundaryError


def trace_root(app, project_id, job_id, attempt):
    # Hash IDs, never splice arbitrary client paths into storage.
    return app.root / "service-data" / "ontology-traces" / semantic_hash(project_id) / semantic_hash(job_id) / str(attempt)


def recorder_factory(app, project, request, principal, job, holder):
    def create(run, session):
        if not app.configuration.ontology_trace_enabled:
            return None
        if not principal.can("trace:record") or not principal.can("source:read"):
            return None
        changes = set()
        params = public_value(request.parameters, changes)
        package_root = Path(__file__).parents[1]
        implementation = {p.relative_to(package_root).as_posix(): digest(p.read_bytes()) for p in sorted(package_root.rglob("*.py"))}
        repo = package_root.parent.parent
        identity = source_identity(repo) if (repo / ".git").exists() else {
            "commit": None, "fingerprint": {"digest": semantic_hash(implementation), "files": implementation},
            "identity_scope": "INSTALLED_SOURCE_BYTES_COMMIT_UNAVAILABLE"}
        frozen = (session or {}).get("frozen", {})
        lock = load_project_lock(Path(project.root)).document
        resources = {
            "tasks": {"operation": request.operation_id, "parameters": params, "session_id": run.session_id},
            "prompts": {"template_source_files": {n: h for n, h in implementation.items() if n.startswith("modeling/five_stage/")},
                        "configuration": public_value(frozen.get("configuration", {}), changes)},
            "tools": {"source_files": implementation, "runtime": runtime_versions()},
            "rules": {"business_rules": frozen.get("business_rules", []), "policy": "EXISTING_SERVICE_AUTHORITY_AND_STAGE_ALLOWLIST"},
            "knowledge": {"input_run_id": frozen.get("run_id"), "dataset_digest": frozen.get("dataset_digest"),
                          "applicability": "FROZEN_INPUT" if frozen else "NOT_APPLICABLE_NO_SESSION_INPUT"},
            "ontology": {"initial_project_lock": lock, "parent_version": run.parent_version},
        }
        harness = freeze_harness(resources, provenance={"source": identity, "runtime": runtime_versions()})
        assistance = request.parameters.get("model_assistance") or {}
        mode = assistance.get("execution_mode", "LIVE" if request.operation_id == "modeling.scope.draft" else
            "RECORDED" if "recorded-model-output-provider" in request.parameters.get("providers", []) else "DETERMINISTIC")
        recorder = TraceRecorder(native_run_id=run.run_id, task_id=run.task_id, task_input=params, harness=harness,
            bindings={"project_id": project.project_id, "job_id": job.job_id, "attempt": job.attempt,
                "fencing_token": job.fencing_token, "principal_id": principal.principal_id,
                "session_id": run.session_id, "session_revision": (session or {}).get("revision"),
                "parent_version": run.parent_version, "execution_mode": mode, "input_snapshot": frozen.get("dataset_digest"),
                "data_policy": app.configuration.ontology_trace_data_policy,
                "source_capture_authorization": "EXPLICIT_SERVER_OPT_IN_AND_TRACE_RECORD_SOURCE_READ"},
            journal=trace_root(app, project.project_id, job.job_id, job.attempt) / (run.run_id.split(":")[-1] + ".jsonl.tmp"))
        recorder.changes.update(changes)
        holder.append(recorder)
        return recorder
    return create


def finish_recorders(holder, *, result=None, error=None, cancelled=False):
    for recorder in holder:
        if recorder.finished:
            continue
        answer = {"kind": "zhigou-operation-result/1.0.0", "execution": "FAILED" if error else "SUCCEEDED",
                  "output_sha256": semantic_hash(result) if result is not None else None,
                  "publication": "NOT_COMMITTED" if error else "COMMITTED_PROJECT_GENERATION",
                  "review": "NOT_GRANTED_BY_TRACE", "release": "NOT_GRANTED_BY_TRACE"}
        recorder.finish("cancelled" if cancelled else "failed" if error else "success", answer,
                        error={"type": type(error).__name__} if error else None)


def load_trace(app, project, principal, job_id):
    job = app._job(job_id, app._current(principal))
    if job.project_id != project.project_id:
        raise ServiceBoundaryError("TRACE_SCOPE_INVALID", "trace belongs to another project", status_code=404)
    if job.status not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        raise ServiceBoundaryError("TRACE_NOT_TERMINAL", "unfinished or lost-lease trace requires reconciliation", status_code=409)
    summary = (job.result or {}).get("agent_execution") or (job.error or {}).get("agent_execution")
    if not summary:
        raise ServiceBoundaryError("TRACE_UNAVAILABLE", "no authorized recorded trace for this job attempt", status_code=409)
    native_id = summary["run_id"]
    require(native_id.startswith("agent-run:") and len(native_id.split(":")[-1]) == 32, "TRACE_ID_INVALID")
    path = trace_root(app, project.project_id, job_id, job.attempt) / (native_id.split(":")[-1] + ".jsonl.json")
    if not path.exists():
        raise ServiceBoundaryError("TRACE_UNAVAILABLE", "content recording was disabled or did not finish", status_code=409)
    raw = read_bounded(path)
    trace = json.loads(raw)
    bound = trace["bindings"]
    require(bound["job_id"] == job_id and bound["attempt"] == job.attempt and bound["fencing_token"] == job.fencing_token
            and bound["project_id"] == project.project_id and bound["native_agent_run_id"] == native_id, "TRACE_JOB_BINDING_MISMATCH")
    require(read_bounded(path.with_suffix(".tmp")) == b"".join(json_bytes(r) for r in trace["events"]), "TRACE_JOURNAL_MISMATCH")
    frozen = trace["harness_manifest"]
    require(freeze_harness(frozen["resources"], provenance=frozen["provenance"])["hashes"] == frozen["hashes"], "TRACE_HARNESS_MISMATCH")
    return trace


def export_trace(app, project, request, principal):
    trace = load_trace(app, project, principal, request.parameters["job_id"])
    if request.parameters.get("profile", "strict-v2") == "local":
        return {"local-trace.json": json_bytes(trace), "protocol-diagnostic.json": json_bytes(trace["protocol"])}, {
            "status": "LOCAL_DIAGNOSTIC_EXPORTED", "format": "zhigou-local-trace/1.0.0",
            "strict_v2": trace["protocol"]["status"], "receiver_status": "NOT_CONTACTED"}
    if trace["protocol"]["errors"]:
        raise ServiceBoundaryError("EVOLUTION_STRICT_V2_BLOCKED", "strict v2 cannot represent this complete trace; export local diagnostics", status_code=409)
    if trace["capture_status"] != "COMPLETE":
        raise ServiceBoundaryError("TRACE_REDACTED_OR_PARTIAL", "redacted or partial messages are not a complete v2 sample", status_code=409)
    reviews = []
    root = Path(project.root) / "artifacts" / "builds" / "trajectory-reviews"
    for path in sorted(root.glob("*.json")) if root.exists() else []:
        record = json.loads(read_bounded(path))
        if record["review"]["exec_id"] == trace["bindings"]["transport_run_id"]:
            require(record["nature"] == "AUTHENTICATED_HUMAN", "SYNTHETIC_REVIEW_NOT_FOR_DELIVERY")
            reviews.append(record["review"])
    files = evolution_files([trace], batch_id=request.parameters["batch_id"], deliverer="zhigou-ontology", reviews=reviews)
    # Project-level no-duplicate ledger is committed by the same CAS transaction.
    ledger = Path(project.root) / "artifacts/builds/trajectory-deliveries" / (trace["bindings"]["transport_run_id"] + ".json")
    receipt = {"batch_id": request.parameters["batch_id"], "files_digest": semantic_hash({n: digest(v) for n, v in files.items()})}
    if ledger.exists():
        require(json.loads(read_bounded(ledger)) == receipt, "DUPLICATE_RUN_DELIVERY")
    else:
        atomic_file(ledger, json_bytes(receipt))
    return files, {"status": "EXPORTED", "format": "evolution-upstream/v2", "receiver_status": "NOT_CONTACTED"}


def submit_review(app, project, request, principal):
    if principal.principal_type != "HUMAN":
        raise ServiceBoundaryError("HUMAN_REVIEW_REQUIRED", "trajectory review requires an authenticated human", status_code=403)
    trace = load_trace(app, project, principal, request.parameters["job_id"])
    run_id = trace["bindings"]["transport_run_id"]
    row = {"review_id": uuid4().hex, "exec_id": run_id, "verdict": request.parameters["verdict"],
           "annotations": request.parameters["annotations"], "reviewer": principal.principal_id, "ts": datetime.now(UTC).isoformat()}
    require(not validate_review(row, {run_id}, producer=True)["errors"], "TRAJECTORY_REVIEW_INVALID")
    nature = "SYNTHETIC_ENGINEERING" if app.configuration.review_profile == "DEVELOPMENT_SINGLE_REVIEWER" else "AUTHENTICATED_HUMAN"
    atomic_file(Path(project.root) / "artifacts/builds/trajectory-reviews" / (row["review_id"] + ".json"), json_bytes({"nature": nature, "review": row}))
    return {"review_id": row["review_id"], "exec_id": run_id, "nature": nature, "status": "RECORDED_NOT_COLLECTED"}
