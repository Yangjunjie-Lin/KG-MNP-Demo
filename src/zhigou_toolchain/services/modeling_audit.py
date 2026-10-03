"""Job-bound step audit files outside project generations, including failures."""
from __future__ import annotations

import json
import logging
from dataclasses import replace

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.delivery.exchange_io import (
    atomic_file,
    checked_path,
    file_rows,
    json_bytes,
    read_bounded,
    require,
)
from zhigou_toolchain.modeling.delivery.trace import CALL_LINK, public_value
from zhigou_toolchain.modeling.five_stage.agents import OPERATION_TO_TOOL, OWNERS
from zhigou_toolchain.modeling.five_stage.audit import ACTIVE_AUDIT, StepAudit
from zhigou_toolchain.modeling.five_stage.coverage import (
    HUMAN_METHOD,
    implementation_view,
    runtime_view,
    token_view,
)
from zhigou_toolchain.modeling.five_stage.prompts import source_catalogue
from zhigou_toolchain.semantic_kernel.packaging.archive import archive_mapping_bytes

from .errors import ServiceBoundaryError
from .modeling_sessions import read
from .projects import get_project, load_catalog, require_access

# Human decisions and independent acceptance are observed, never Agent tools.
SPECIAL_OPERATIONS = {
    "modeling.scenario.save": (1, "AUTHORIZED_SCENARIO_CONFIGURATION"),
    "modeling.scenario.quality": (5, "INDEPENDENT_ACCEPTANCE_SERVICE"),
    "modeling.expert.save": (1, "AUTHORIZED_EXPERT_CONFIGURATION"),
    "modeling.expert.reaudit": (1, "TWO_AGENT_REVIEW_OPERATION"),
    "modeling.session.open": (1, "AUTHORIZED_INPUT_OWNER"),
    "modeling.session.revise": (1, "AUTHORIZED_INPUT_OWNER"),
    "modeling.scope.approve": (1, "AUTHORIZED_REVIEWER"),
    "review.action": (4, "AUTHORIZED_REVIEWER"),
    "review.replay": (4, "SERVICE_OBSERVATION"),
    "review.finalize": (4, "AUTHORIZED_REVIEWER"),
    "modeling.handoff.check": (5, "INDEPENDENT_ACCEPTANCE_SERVICE"),
    "modeling.evolution.export": (5, "AUTHORIZED_EXPORT_SERVICE"),
    "modeling.evolution.review": (5, "AUTHORIZED_REVIEWER"),
    "modeling.handoff.import": (1, "AUTHORIZED_INPUT_SERVICE"),
    "modeling.tutorial.seed": (1, "SYNTHETIC_INPUT_SERVICE"),
    "modeling.proposal": (3, "TWO_AGENT_OPERATION"),
    "modeling.candidate": (3, "TWO_AGENT_OPERATION"),
}


def operation_role(operation):
    if operation in OPERATION_TO_TOOL:
        stage, _ = OPERATION_TO_TOOL[operation]
        return stage, OWNERS[stage]
    return SPECIAL_OPERATIONS.get(operation)


def audit_root(service, project_id, job_id, attempt):
    return service.root / "service-data" / "modeling-step-audits" / semantic_hash(project_id) / semantic_hash(job_id) / str(attempt)


def session_state(project):
    session = read(project.root)
    frozen = (session or {}).get("frozen", {})
    return {"authority_revision": project.authority_revision,
            "session_id": (session or {}).get("session_id"), "session_revision": (session or {}).get("revision"),
            "input_run_id": frozen.get("run_id"), "input_snapshot_sha256": frozen.get("dataset_digest"),
            "session_sha256": semantic_hash(session), "outputs": (session or {}).get("outputs", []),
            "checks": (session or {}).get("checks", [])}


def observe_computed_state(project):
    audit = ACTIVE_AUDIT.get()
    if audit is not None:
        audit.computed_state = session_state(project)


def recording_failure(service, job, principal, error, channel):
    """Report to the existing low-sensitivity platform audit, not job truth."""
    try:
        service.audit.append(principal_id=principal.principal_id, operation_id=job.operation_id,
            project_id=job.project_id, request_id=job.job_id, outcome="AUDIT_RECORDING_INCOMPLETE",
            details={"attempt": job.attempt, "channel": channel, "error_type": type(error).__name__,
                "business_commit": "REQUIRES_NATIVE_RECEIPT_CHECK"})
    except Exception:  # noqa: BLE001 - recording errors must not mask native commit/recovery
        logging.getLogger(__name__).error("AUDIT_RECORDING_INCOMPLETE channel=%s", channel)


def execute_audited(service, job, request, principal, action):
    role = operation_role(request.operation_id)
    if request.operation_id == "modeling.expert.save":
        role = (request.parameters["configuration"]["stage"], "AUTHORIZED_EXPERT_CONFIGURATION")
    if role is None:
        return action()
    # Recovery reuses the exact original receipt; it is not a new execution.
    from .execution import committed_result
    replay = committed_result(service, job)
    if replay is not None:
        return replay
    project = get_project(service.root, job.project_id)
    state = session_state(project)
    binding = {"project_id": job.project_id, "job_id": job.job_id, "attempt": job.attempt,
               "fencing_token": job.fencing_token, "request_digest": job.request_digest,
               "operation_id": request.operation_id, "principal_id": principal.principal_id,
               "principal_type": principal.principal_type, "review_profile": service.configuration.review_profile,
               "capture_configuration": {
                   "step_content_enabled": service.configuration.modeling_audit_content_enabled,
                   "model_trace_enabled": service.configuration.ontology_trace_enabled,
                   "record_authorized": principal.can("trace:record") and principal.can("source:read")}}
    catalogue = None
    if (service.configuration.modeling_audit_content_enabled or service.configuration.ontology_trace_enabled) and binding["capture_configuration"]["record_authorized"]:
        catalogue_changes = set()
        catalogue = public_value(source_catalogue(), catalogue_changes)
        binding.update(prompt_catalogue_sha256=semantic_hash(catalogue),
            prompt_catalogue_capture="REDACTED" if catalogue_changes else "CAPTURED")
    else:
        binding["prompt_catalogue_capture"] = "NOT_RECORDED"
    audit = StepAudit(audit_root(service, job.project_id, job.job_id, job.attempt), binding,
        content=service.configuration.modeling_audit_content_enabled and principal.can("trace:record") and principal.can("source:read"))
    if catalogue is not None:
        atomic_file(audit.directory / "prompts" / "catalogue.json", json_bytes(catalogue))
    call_id = audit.before({"kind": "OPERATION", "stage_id": role[0], "actor": role[1],
                            "method_id": HUMAN_METHOD.get(request.operation_id),
                            "authority": "OBSERVATION_ONLY", "state": state}, request.parameters)
    token = ACTIVE_AUDIT.set(audit)
    link_token = CALL_LINK.set({"parent_audit_call_id": call_id})
    try:
        result = action()
        try:
            audit.after(call_id, {"result": result, "computed_state": audit.computed_state}, status="COMMITTED",
                        outcome={"committed_result_sha256": semantic_hash(result)})
        except Exception as exc:  # noqa: BLE001 - post-commit audit is not rollback authority
            recording_failure(service, job, principal, exc, "STEP_AFTER_COMMIT")
        return result
    except BaseException as exc:
        status = "CANCELLED" if service.jobs.get(job.job_id).status in {"CANCELLED", "CANCEL_REQUESTED"} else "FAILED_NOT_COMMITTED"
        # A commit may already exist if the response was lost. Do not invent a rollback.
        if job.job_id in load_catalog(service.root).get("commits", {}):
            status = "COMMIT_REQUIRES_RECONCILIATION"
        if call_id in audit.pending:
            try:
                audit.after(call_id, {"computed_state": audit.computed_state}, status=status, error=exc)
            except Exception as audit_error:  # noqa: BLE001 - preserve the original computation failure
                recording_failure(service, job, principal, audit_error, "STEP_FAILURE")
        raise
    finally:
        CALL_LINK.reset(link_token)
        ACTIVE_AUDIT.reset(token)
        try:
            audit.close_index()
        except Exception as exc:  # noqa: BLE001 - index failure cannot replace native outcome
            recording_failure(service, job, principal, exc, "STEP_INDEX")


def _authorized(service, principal, project_id):
    principal = service._current(principal)
    if not all(principal.can(p) for p in ("project:read", "job:read")):
        raise ServiceBoundaryError("FORBIDDEN", "project:read and job:read required", status_code=403)
    require_access(principal, get_project(service.root, project_id))
    return principal


def read_events(service, job):
    root = checked_path(audit_root(service, job.project_id, job.job_id, job.attempt))
    paths = sorted(root.glob("??????-*.json"))
    require(len(paths) <= 20000, "STEP_AUDIT_LIMIT")
    events, previous, size = [], None, 0
    identity = service.jobs.parameters(job.job_id).get("__principal", {})
    actor_identity = service.tokens.audit_identity(identity.get("token_id", ""))
    for index, path in enumerate(paths, 1):
        raw = read_bounded(path)
        size += len(raw)
        require(size <= 64_000_000, "STEP_AUDIT_LIMIT")
        row = json.loads(raw)
        require(row["sequence"] == index and row["previous_event_sha256"] == previous
                and row["event_sha256"] == semantic_hash({k: v for k, v in row.items() if k != "event_sha256"}), "STEP_AUDIT_CHAIN_INVALID")
        bound = row["binding"]
        require(all(bound[k] == getattr(job, k) for k in ("project_id", "job_id", "attempt", "fencing_token", "request_digest", "operation_id")), "STEP_AUDIT_BINDING_INVALID")
        for key in ("principal_id", "principal_type"):
            if key in bound:
                require(bound[key] == actor_identity.get(key), "STEP_AUDIT_ACTOR_MISMATCH")
        previous = row["event_sha256"]
        events.append(row)
    return events


def attempt_record(service, job, attempt):
    """Recover old lease identity from native JobStore events, not audit claims."""
    if attempt == job.attempt:
        return job
    claims = [e for e in service.jobs.events(job.job_id) if e["event_type"] == "JOB_CLAIMED"]
    if type(attempt) is not int or not 1 <= attempt < job.attempt or attempt > len(claims):
        raise ServiceBoundaryError("STEP_AUDIT_ATTEMPT_INVALID", "unknown execution attempt", status_code=404)
    return replace(job, attempt=attempt, fencing_token=claims[attempt - 1]["payload"]["fencing_token"],
                   status="SUPERSEDED_ATTEMPT", result=None, error=None)


def audit_index(service, principal, project_id, *, session_id=None, package_id=None, job_id=None, attempt=None):
    principal = _authorized(service, principal, project_id)
    current = read(get_project(service.root, project_id).root)
    selected_jobs = None
    if package_id is not None:
        from zhigou_toolchain.modeling.delivery.bindings import require_handoff_head

        from .handoff import observations_for
        require_handoff_head(current, package_id, (current or {}).get("revision"))
        assert current is not None
        selected_jobs = {o["job_id"] for o in observations_for(service, get_project(service.root, project_id), current)}
        selected_jobs.update(o["job_id"] for o in current["outputs"] if o["status"] == "CURRENT")
    output_status = {o["job_id"]: o["status"] for o in (current or {}).get("outputs", [])}
    records = []
    for job in service.jobs.list_project(project_id):
        if (job_id is not None and job.job_id != job_id) or (selected_jobs is not None and job.job_id not in selected_jobs):
            continue
        role = operation_role(job.operation_id)
        if not role:
            continue
        try:
            service._job(job.job_id, principal)
        except ServiceBoundaryError:
            continue
        for number in range(job.attempt, 0, -1) if job.attempt else [0]:
            if attempt is not None and number != attempt:
                continue
            attempted = attempt_record(service, job, number)
            root = audit_root(service, project_id, job.job_id, number)
            summary_path = root / "summary.json"
            summary = json.loads(read_bounded(summary_path)) if summary_path.exists() else {}
            events = read_events(service, attempted)
            state = events[0]["metadata"].get("state", {}) if events else {}
            if session_id is not None and state.get("session_id") != session_id:
                continue
            records.append({"job_id": job.job_id, "operation_id": job.operation_id, "attempt": number,
                "stage_id": role[0], "actor": role[1], "job_status": attempted.status,
                "session_id": state.get("session_id"), "session_revision": state.get("session_revision"),
                "capture_configuration": events[0]["binding"].get("capture_configuration") if events else None,
                "method_ids": sorted({e["metadata"]["method_id"] for e in events if e["metadata"].get("method_id")}),
                "physical_requests": sum(e["metadata"]["kind"] == "MODEL" and e["phase"] == "AFTER"
                    and e["metadata"].get("dispatch_status") == "TRANSPORT_ATTEMPTED" for e in events),
                "physical_request_scope": "TRANSPORT_BOUNDARY_ATTEMPTS_SEE_DETAIL_FOR_NOT_SENT_OR_INTERRUPTED",
                "stages": summary.get("stages", [role[0]]), "event_count": summary.get("event_count"),
                "content_mode": summary.get("content_mode", "NOT_CONFIRMED"),
                "session_output_status": output_status.get(job.job_id, "NOT_A_CURRENT_SESSION_OUTPUT") if number == job.attempt else "SUPERSEDED_ATTEMPT",
                "availability": "AVAILABLE" if root.exists() and any(root.glob("??????-*.json")) else "ARTIFACT_NOT_AVAILABLE"})
    _authorized(service, principal, project_id)
    return {"format": "zhigou-step-audit-index/1.0.0", "records": records,
            "content_capture_enabled": service.configuration.modeling_audit_content_enabled,
            "model_trace_enabled": service.configuration.ontology_trace_enabled,
            "implementation": implementation_view(),
            "selection": {"session_id": session_id, "package_id": package_id, "job_id": job_id, "attempt": attempt},
            "authority": "OBSERVATION_ONLY"}


def download_audit(service, principal, project_id, job_id, *, attempt=None):
    principal = _authorized(service, principal, project_id)
    if not all(principal.can(p) for p in ("trace:export", "source:read", "source:export", "package:read")):
        raise ServiceBoundaryError("FORBIDDEN", "trace:export, source:read, source:export and package:read required", status_code=403)
    job = service._job(job_id, principal)
    if job.project_id != project_id:
        raise ServiceBoundaryError("JOB_NOT_FOUND", "audit belongs to another project", status_code=404)
    job = attempt_record(service, job, attempt if attempt is not None else job.attempt)
    if job.status not in {"SUCCEEDED", "FAILED", "CANCELLED", "RECOVERY_REQUIRED", "SUPERSEDED_ATTEMPT"}:
        raise ServiceBoundaryError("STEP_AUDIT_NOT_TERMINAL", "wait for this job attempt to stop", status_code=409)
    events = read_events(service, job)
    if not events:
        raise ServiceBoundaryError("STEP_AUDIT_UNAVAILABLE", "historical before/after content was not recorded", status_code=404)
    params = {k: v for k, v in service.jobs.parameters(job.job_id).items() if k != "__principal"}
    require(events[0]["phase"] == "BEFORE" and events[0]["metadata"]["kind"] == "OPERATION"
            and events[0]["payload"]["semantic_sha256"] == semantic_hash(params), "STEP_AUDIT_REQUEST_MISMATCH")
    if "value" in events[0]["payload"]:
        require(events[0]["payload"]["value"] == public_value(params, set()), "STEP_AUDIT_REQUEST_MISMATCH")
    pending = {}
    for event in events:
        cid = event["call_id"]
        if event["phase"] == "BEFORE":
            require(cid not in pending, "STEP_AUDIT_PAIR_INVALID")
            pending[cid] = event
        else:
            require(event["phase"] == "AFTER" and cid in pending, "STEP_AUDIT_PAIR_INVALID")
            del pending[cid]
    from .execution import committed_result
    commit = load_catalog(service.root).get("commits", {}).get(job.job_id)
    committed = committed_result(service, job) if commit and commit["context"]["attempt"] == job.attempt else None
    if committed is not None and "step_audit_anchor" in committed:
        anchor = committed["step_audit_anchor"]
        require(anchor["job_id"] == job.job_id and anchor["attempt"] == job.attempt
            and 0 < anchor["event_count"] <= len(events)
            and events[anchor["event_count"] - 1]["event_sha256"] == anchor["event_sha256"], "STEP_AUDIT_COMMITTED_ANCHOR_MISMATCH")
    end = next((e for e in reversed(events) if e["metadata"]["kind"] == "OPERATION" and e["phase"] == "AFTER"), None)
    if end and end["metadata"]["status"] == "COMMITTED":
        require(committed is not None, "STEP_AUDIT_COMMIT_MISSING")
        assert committed is not None and commit is not None
        require(end["metadata"]["committed_result_sha256"] == semantic_hash(committed), "STEP_AUDIT_RESULT_MISMATCH")
        frozen_project = replace(get_project(service.root, project_id), root=commit["root"], authority_revision=commit["authority_revision"])
        expected = {"result": committed, "computed_state": session_state(frozen_project)}
        require(end["payload"]["semantic_sha256"] == semantic_hash(expected), "STEP_AUDIT_STATE_MISMATCH")
        if "value" in end["payload"]:
            require(end["payload"]["value"] == public_value(expected, set()), "STEP_AUDIT_STATE_MISMATCH")
    if committed is not None:
        tool_starts = [e for e in events if e["phase"] == "BEFORE" and e["metadata"]["kind"] == "TOOL"]
        native = committed.get("agent_execution", {})
        require(len(tool_starts) == len(native.get("records", [])), "STEP_AUDIT_NATIVE_RUN_MISMATCH")
        native_by_start = {r.get("audit_before_sha256"): r for r in native.get("records", [])}
        for event in tool_starts:
            require(event["event_sha256"] in native_by_start, "STEP_AUDIT_NATIVE_RUN_MISMATCH")
            record = native_by_start[event["event_sha256"]]
            require(event["metadata"]["native_agent_run_id"] == native["run_id"]
                    and event["event_sha256"] == record.get("audit_before_sha256")
                    and event["metadata"]["actor"] == record["agent_id"]
                    and event["metadata"]["tool_id"] == record["tool_id"]
                    and event["metadata"]["stage_id"] == record["stage_id"]
                    and event["payload"]["semantic_sha256"] == record["input_sha256"], "STEP_AUDIT_NATIVE_RUN_MISMATCH")
            ended = next((e for e in events if e["call_id"] == event["call_id"] and e["phase"] == "AFTER"), None)
            require(ended is not None and ended["metadata"]["status"] == record["status"], "STEP_AUDIT_NATIVE_RUN_MISMATCH")
            assert ended is not None
            require(ended["event_sha256"] == record.get("audit_after_sha256"), "STEP_AUDIT_NATIVE_RUN_MISMATCH")
            if record["output_sha256"] is not None:
                require(ended["payload"]["semantic_sha256"] == record["output_sha256"], "STEP_AUDIT_NATIVE_RUN_MISMATCH")
        model_starts = {e["call_id"]: e for e in events if e["phase"] == "BEFORE" and e["metadata"]["kind"] == "MODEL"}
        witnesses = [(r, c) for r in native.get("records", []) for c in r.get("model_calls", [])]
        require(len(model_starts) == len(witnesses), "STEP_AUDIT_MODEL_COUNT_MISMATCH")
        for parent, witness in witnesses:
            start = model_starts.get(witness["audit_call_id"])
            require(start is not None and start["event_sha256"] == witness["audit_before_sha256"], "STEP_AUDIT_MODEL_BINDING_MISMATCH")
            assert start is not None
            require(start["metadata"]["parent_audit_call_id"] == parent["audit_call_id"]
                and start["metadata"]["method_id"] == parent["method_id"], "STEP_AUDIT_MODEL_PARENT_MISMATCH")
            ended = next((e for e in events if e["call_id"] == start["call_id"] and e["phase"] == "AFTER"), None)
            require(ended is not None and ended["event_sha256"] == witness.get("audit_after_sha256"), "STEP_AUDIT_MODEL_RESULT_MISMATCH")
    native = (committed or job.result or {}).get("agent_execution") or (job.error or {}).get("agent_execution") or {}
    trace = _attempt_trace(service, job, events, native, committed=committed)
    files = {f"steps/{e['sequence']:06d}-{e['phase'].lower()}.json": json_bytes(e) for e in events}
    files["journal.jsonl"] = b"".join(json_bytes(e) for e in events)
    result = committed or {}
    step_runs = result.get("five_stage", {}).get("step_runs", []) + result.get("automatic_validation", {}).get("five_stage", {}).get("step_runs", [])
    files["coverage.json"] = json_bytes(runtime_view(events, native=native, trace=trace, parameters=params, step_runs=step_runs))
    files["audits/token_usage.json"] = json_bytes(token_view(events, trace))
    catalogue_path = audit_root(service, project_id, job.job_id, job.attempt) / "prompts" / "catalogue.json"
    if catalogue_path.exists():
        catalogue_raw = read_bounded(catalogue_path)
        require(semantic_hash(json.loads(catalogue_raw)) == events[0]["binding"].get("prompt_catalogue_sha256"), "STEP_PROMPT_CATALOGUE_MISMATCH")
        files["prompts/run-source-catalogue.json"] = catalogue_raw
    if trace is not None:
        files["model-trace.json"] = json_bytes(trace)
    if result.get("expert_loop"):
        files["audits/expert-loop.json"] = json_bytes(result["expert_loop"])
    if result.get("scenario_outputs"):
        files["audits/scenario-outputs.json"] = json_bytes(result["scenario_outputs"])
    files["README.md"] = (b"# Modeling step audit\n\nBefore/after observations for one real job attempt.\n"
        b"RuleAgent = planning agent (S1/S2/S4); TaskExecutionAgent = execution agent (S3/S5).\n"
        b"Human review and independent acceptance remain separate authorities.\n"
        b"METADATA_ONLY/REDACTED/OMITTED_SIZE_LIMIT are not lossless content. Missing pairs mean INTERRUPTED, not success.\n"
        b"The hash chain detects corruption, not authorization by itself. Trust the service job/commit authority.\n")
    manifest = {"format": "zhigou-modeling-step-audit/1.0.0", "binding": events[0]["binding"],
        "job_status": job.status, "commit_status": "COMMITTED" if committed is not None else "NOT_COMMITTED",
        "pair_status": "INTERRUPTED" if pending else "CLOSED", "pending_call_ids": sorted(pending),
        "final_event_sha256": events[-1]["event_sha256"], "event_hash_algorithm": "KG-MNP Canonical JSON v1 / SHA-256 (excluding event_sha256)",
        "file_hash_algorithm": "SHA-256 of exact bytes", "files": file_rows(files),
        "approval": "NOT_GRANTED_BY_AUDIT", "release": "NOT_GRANTED_BY_AUDIT", "external_protocol": "PROJECT_LOCAL_NOT_EVOLUTION_V2"}
    files["manifest.json"] = json_bytes(manifest)
    require(sum(map(len, files.values())) <= 128_000_000, "STEP_AUDIT_EXPORT_LIMIT")
    # Recheck revocation after potentially expensive commit/source verification.
    current_actor = _authorized(service, principal, project_id)
    require(all(current_actor.can(p) for p in ("trace:export", "source:read", "source:export", "package:read")), "STEP_AUDIT_PERMISSION_REVOKED")
    service._job(job_id, current_actor)
    return archive_mapping_bytes(files)


def _attempt_trace(service, job, events, native, *, committed=None):
    """Only this native run/attempt; never fill holes from a later success."""
    from zhigou_toolchain.modeling.delivery.bindings import validate_trace_context

    from .ontology_traces import trace_root
    run_id = native.get("run_id")
    if not run_id:
        return None
    path = trace_root(service, job.project_id, job.job_id, job.attempt) / (run_id.split(":")[-1] + ".jsonl.json")
    if not path.exists():
        return None
    trace = json.loads(read_bounded(path))
    bound = trace["bindings"]
    require(all(bound[k] == getattr(job, k) for k in ("project_id", "job_id", "attempt", "fencing_token"))
        and bound["native_agent_run_id"] == run_id, "STEP_TRACE_ATTEMPT_MISMATCH")
    require(read_bounded(path.with_suffix(".tmp")) == b"".join(json_bytes(e) for e in trace["events"]), "TRACE_JOURNAL_MISMATCH")
    require(trace["protocol"] == validate_trace_context(trace), "TRACE_PROTOCOL_REPORT_MISMATCH")
    if bound.get("answer_capture") == "OPERATION_RESULT_V1":
        require(bound["operation_result_digest"] == semantic_hash(committed)
            and trace["events"][-1]["answer"] == public_value(committed, set()), "TRACE_RESULT_BINDING_MISMATCH")
    witnesses = {c["transport_call_id"]: c for r in native.get("records", []) for c in r.get("model_calls", []) if c.get("transport_call_id")}
    calls = [e for e in trace["events"] if e["event"] == "llm_call"]
    # Legacy captures lack cross-layer witnesses: keep their historical scope.
    if any(e["metadata"]["kind"] == "MODEL" for e in events):
        require(len(calls) == len(witnesses), "STEP_TRACE_MODEL_COUNT_MISMATCH")
        for call in calls:
            witness = witnesses.get(call["call_id"])
            require(witness is not None and all(call.get(k) == witness.get(k) for k in (
                "audit_call_id", "parent_audit_call_id", "method_id", "request_sha256", "messages_sha256", "schema_sha256", "prompt")), "STEP_TRACE_MODEL_LINK_MISMATCH")
            assert witness is not None
            output = next((e for e in trace["events"] if e["event"] == "llm_output" and e["call_id"] == call["call_id"]), None)
            if "transport_request_event_sha256" in witness:
                require(semantic_hash(call) == witness["transport_request_event_sha256"]
                    and output is not None and semantic_hash(output) == witness["transport_output_event_sha256"], "STEP_TRACE_CAPTURE_CHANGED")
            prompt_sources = trace["harness_manifest"]["resources"]["prompts"]
            sources = {**prompt_sources.get("template_source_files", {}), **prompt_sources.get("catalogue", {}).get("source_files", {})}
            require(sources.get(call["prompt"]["wrapper_source"]) == call["prompt"]["wrapper_sha256"]
                and all(sources.get(t["source"]) == t["source_sha256"] for t in call["prompt"]["template_refs"]), "STEP_TRACE_PROMPT_SOURCE_MISMATCH")
            if trace["capture_status"] == "COMPLETE":
                require(semantic_hash({**call["request_parameters"], "messages": call["messages"]}) == call["request_sha256"]
                    and semantic_hash(call["output_schema"]) == call["schema_sha256"]
                    and semantic_hash(call["task"]) == call["prompt"]["task_sha256"], "STEP_TRACE_REQUEST_MISMATCH")
                after = next((e for e in events if e["phase"] == "AFTER" and e["call_id"] == call["audit_call_id"]), None)
                require(output is not None and after is not None and after["payload"]["semantic_sha256"] == semantic_hash({
                    "public_response_sha256": semantic_hash(output.get("public_response", output["content"])),
                    "content_sha256": semantic_hash(output["content"]),
                    "local_validation_sha256": semantic_hash(output.get("local_validation"))}), "STEP_TRACE_RESPONSE_MISMATCH")
    return trace


def audit_detail(service, principal, project_id, job_id, *, attempt=None):
    """Same authorized server snapshot as download, not a frontend ZIP builder."""
    from zhigou_toolchain.modeling.delivery.exchange_io import digest, read_archive
    raw = download_audit(service, principal, project_id, job_id, attempt=attempt)
    files = read_archive(raw)
    return {"archive_sha256": digest(raw), "size_bytes": len(raw),
        "manifest": json.loads(files["manifest.json"]), "coverage": json.loads(files["coverage.json"]),
        "token_usage": json.loads(files["audits/token_usage.json"]),
        "events": [json.loads(line) for line in files["journal.jsonl"].splitlines()],
        "current_templates": public_value(source_catalogue(), set()),
        "run_templates": json.loads(files["prompts/run-source-catalogue.json"]) if "prompts/run-source-catalogue.json" in files else None,
        "actual_model_trace": json.loads(files["model-trace.json"]) if "model-trace.json" in files else None}
