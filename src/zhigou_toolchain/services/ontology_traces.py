"""Private trace journal and authenticated export, never a second job authority."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.delivery.bindings import (
    require_handoff_head,
    validate_trace_context,
)
from zhigou_toolchain.modeling.delivery.evolution import (
    evolution_files,
    parse_jsonl,
    validate_events,
    validate_review,
)
from zhigou_toolchain.modeling.delivery.exchange_io import (
    atomic_file,
    digest,
    json_bytes,
    read_archive,
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
        # Preserve the actual service output, including artifact references. The
        # existing recorder filters private material and marks redacted captures.
        recorder.bindings.update(answer_capture="OPERATION_RESULT_V1",
            operation_result_digest=semantic_hash(result))
        recorder.finish("cancelled" if cancelled else "failed" if error else "success", result,
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
    validate_trace_context(trace)
    if bound.get("answer_capture") == "OPERATION_RESULT_V1":
        from .execution import committed_result
        result = committed_result(app, job) if job.status == "SUCCEEDED" else None
        require(bound["operation_result_digest"] == semantic_hash(result), "TRACE_RESULT_BINDING_MISMATCH")
        require(trace["events"][-1]["answer"] == public_value(result, set()), "TRACE_ANSWER_MISMATCH")
    return trace


def known_export_runs(app, project, principal, job_ids):
    """Resolve historical references from authenticated committed snapshots only.

    This is local reference evidence, NEVER a receiver collection receipt.
    Caller-supplied run IDs or optional context cannot establish trust.
    """
    from .execution import committed_result
    from .projects import load_catalog, require_access
    actor = app._current(principal)
    require_access(actor, project)
    if not actor.can("source:read") or not (actor.can("trace:review") or actor.can("trace:export")):
        raise ServiceBoundaryError("FORBIDDEN", "historical trace references require source and trace permission", status_code=403)
    runs = {}
    for job_id in job_ids:
        job = app._job(job_id, actor)
        require(job.project_id == project.project_id and job.operation_id == "modeling.evolution.export", "HISTORICAL_EXPORT_SCOPE_INVALID")
        receipt = committed_result(app, job)
        require(receipt and receipt.get("status") == "EXPORTED" and receipt.get("format") == "evolution-upstream/v2", "HISTORICAL_EXPORT_REQUIRED")
        assert receipt is not None
        generation = Path(load_catalog(app.root)["commits"][job_id]["root"])
        raw = read_bounded(generation / "artifacts/builds/handoff" / (receipt["sha256"] + ".zip"))
        require(digest(raw) == receipt["sha256"] and len(raw) == receipt["size_bytes"], "EXPORT_BYTES_CHANGED")
        files = read_archive(raw)
        for name, content in files.items():
            if not name.startswith("executions/run-") or not name.endswith(".jsonl"):
                continue
            run_id = name[len("executions/run-"):-len(".jsonl")]
            require(not validate_events(parse_jsonl(content), run_id, producer=True)["errors"], "HISTORICAL_EXECUTION_INVALID")
            previous = runs.get(run_id)
            require(previous is None or previous["sha256"] == digest(content), "HISTORICAL_EXECUTION_CONFLICT")
            runs[run_id] = {"export_job_id": job_id, "sha256": digest(content),
                "reference_status": "LOCAL_COMMITTED_EXPORT", "receiver_status": "NOT_CONTACTED"}
    current = app._current(principal)
    require_access(current, project)
    if not current.can("source:read") or not (current.can("trace:review") or current.can("trace:export")):
        raise ServiceBoundaryError("FORBIDDEN", "historical trace permission changed", status_code=403)
    for job_id in job_ids:
        app._job(job_id, current)
    return runs


def selected_reviews(app, project, principal, params, run_id=None):
    root = Path(project.root) / "artifacts/builds/trajectory-reviews"
    selected = set(params.get("review_ids", []))
    require(len(selected) == len(params.get("review_ids", [])), "DUPLICATE_REVIEW_ID")
    found, reviews, export_ids = set(), [], set(params.get("known_run_export_job_ids", []))
    for path in sorted(root.glob("*.json")) if root.exists() else []:
        record = json.loads(read_bounded(path))
        row = record["review"]
        if row["review_id"] not in selected and (run_id is None or row["exec_id"] != run_id):
            continue
        require(record["nature"] == "AUTHENTICATED_HUMAN", "SYNTHETIC_REVIEW_NOT_FOR_DELIVERY")
        require(path.stem == row["review_id"], "REVIEW_ID_BINDING_MISMATCH")
        found.add(row["review_id"])
        reviews.append(row)
        if record.get("execution_export_job_id"):
            export_ids.add(record["execution_export_job_id"])
    require(selected.issubset(found), "REVIEW_NOT_FOUND")
    known = known_export_runs(app, project, principal, sorted(export_ids))
    return reviews, known


def commit_batch(project, params, files, run_ids, review_ids):
    # Reuse the original CAS-committed project delivery ledger for both IDs.
    root = Path(project.root) / "artifacts/builds/trajectory-deliveries"
    receipt = {"batch_id": params["batch_id"], "files_digest": semantic_hash({n: digest(v) for n, v in files.items()})}
    keys = [*run_ids, *("review-" + semantic_hash(i) for i in review_ids), "batch-" + semantic_hash(params["batch_id"])]
    for key in keys:
        ledger = root / (key + ".json")
        if ledger.exists():
            require(json.loads(read_bounded(ledger)) == receipt, "DUPLICATE_RUN_OR_REVIEW_DELIVERY")
        else:
            atomic_file(ledger, json_bytes(receipt))


def export_trace(app, project, request, principal):
    if not request.parameters.get("job_id"):
        reviews, known = selected_reviews(app, project, principal, request.parameters)
        files = evolution_files([], batch_id=request.parameters["batch_id"], deliverer="zhigou-ontology", reviews=reviews, known_run_ids=known)
        commit_batch(project, request.parameters, files, [], [r["review_id"] for r in reviews])
        return files, {"status": "EXPORTED", "format": "evolution-upstream/v2", "receiver_status": "NOT_CONTACTED",
            "reference_check": "LOCAL_PRECHECK_NOT_COLLECTION", "review_ids": [r["review_id"] for r in reviews]}
    trace = load_trace(app, project, principal, request.parameters["job_id"])
    target_package = request.parameters.get("target_package_id")
    if target_package:
        from zhigou_toolchain.semantic_kernel.packaging.archive import (
            archive_mapping_bytes,
            read_verified_package_files,
        )

        from .compilation import package_location
        from .handoff import observations_for
        from .modeling_sessions import read
        session = read(project.root)
        require_handoff_head(session, target_package, request.parameters.get("expected_revision"))
        assert session is not None
        observed = next((o for o in observations_for(app, project, session) if o["job_id"] == request.parameters["job_id"]), None)
        require(observed is not None, "DELIVERY_RUN_REFERENCE_MISSING")
        assert observed is not None
        native, _ = read_verified_package_files(package_location(project, target_package), expected_package_id=target_package)
        confirmed = json.loads(native["source/confirmed-modeling-package.json"])
        plan = json.loads(native["source/semantic-compilation-plan.json"])
        trace["bindings"].update(delivery_target={"project_id": project.project_id, "session_id": session["session_id"], "session_revision": session["revision"],
            "input_run_id": session["frozen"]["run_id"], "input_snapshot": session["frozen"]["dataset_digest"],
            "confirmed_package_id": confirmed["package_id"], "compilation_plan_id": plan["plan_id"], "compiler_snapshot_id": plan["compiler_snapshot_id"],
            "package_id": target_package, "native_archive_sha256": digest(archive_mapping_bytes(native))},
            output_artifacts=[observed["session_output"]], committed_result_digest=observed["result_digest"])
    if request.parameters.get("profile", "strict-v2") == "local":
        return {"local-trace.json": json_bytes(trace), "protocol-diagnostic.json": json_bytes(trace["protocol"]),
                "journal.jsonl": b"".join(json_bytes(r) for r in trace["events"])}, {
            "status": "LOCAL_DIAGNOSTIC_EXPORTED", "format": "zhigou-local-trace/1.0.0",
            "strict_v2": trace["protocol"]["status"], "receiver_status": "NOT_CONTACTED"}
    if trace["protocol"]["errors"]:
        raise ServiceBoundaryError("EVOLUTION_STRICT_V2_BLOCKED", "strict v2 cannot represent this complete trace; export local diagnostics", status_code=409)
    if trace["bindings"].get("execution_mode") != "LIVE":
        raise ServiceBoundaryError("NON_LIVE_TRACE_NOT_COLLECTIBLE", "recorded/program traces are local diagnostics only", status_code=409)
    if trace["capture_status"] != "COMPLETE":
        raise ServiceBoundaryError("TRACE_REDACTED_OR_PARTIAL", "redacted or partial messages are not a complete v2 sample", status_code=409)
    run_id = trace["bindings"]["transport_run_id"]
    reviews, known = selected_reviews(app, project, principal, request.parameters, run_id)
    files = evolution_files([trace], batch_id=request.parameters["batch_id"], deliverer="zhigou-ontology", reviews=reviews, known_run_ids=known)
    commit_batch(project, request.parameters, files, [run_id], [r["review_id"] for r in reviews])
    return files, {"status": "EXPORTED", "format": "evolution-upstream/v2", "receiver_status": "NOT_CONTACTED"}


def submit_review(app, project, request, principal):
    principal = app._current(principal)
    if principal.principal_type != "HUMAN":
        raise ServiceBoundaryError("HUMAN_REVIEW_REQUIRED", "trajectory review requires an authenticated human", status_code=403)
    params = request.parameters
    export_id = params.get("execution_export_job_id")
    if params.get("job_id"):
        trace = load_trace(app, project, principal, params["job_id"])
        run_id = trace["bindings"]["transport_run_id"]
    else:
        known = known_export_runs(app, project, principal, [export_id])
        run_id = params["exec_id"]
        require(run_id in known, "REVIEW_EXECUTION_MISSING")
    row = {"review_id": uuid4().hex, "exec_id": run_id, "verdict": request.parameters["verdict"],
           "reviewer": principal.principal_id, "ts": datetime.now(UTC).isoformat()}
    row.update({k: params[k] for k in ("annotations", "violations", "corrected_answer") if k in params})
    require(not validate_review(row, {run_id}, producer=True)["errors"], "TRAJECTORY_REVIEW_INVALID")
    nature = "SYNTHETIC_ENGINEERING" if app.configuration.review_profile == "DEVELOPMENT_SINGLE_REVIEWER" else "AUTHENTICATED_HUMAN"
    atomic_file(Path(project.root) / "artifacts/builds/trajectory-reviews" / (row["review_id"] + ".json"),
        json_bytes({"nature": nature, "review": row, "execution_export_job_id": export_id}))
    return {"review_id": row["review_id"], "exec_id": run_id, "nature": nature, "status": "RECORDED_NOT_COLLECTED"}
