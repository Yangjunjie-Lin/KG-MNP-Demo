"""Job-bound step audit files outside project generations, including failures."""
from __future__ import annotations

import json
from dataclasses import replace

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.delivery.exchange_io import (
    checked_path,
    file_rows,
    json_bytes,
    read_bounded,
    require,
)
from zhigou_toolchain.modeling.delivery.trace import public_value
from zhigou_toolchain.modeling.five_stage.agents import OPERATION_TO_TOOL, OWNERS
from zhigou_toolchain.modeling.five_stage.audit import ACTIVE_AUDIT, StepAudit
from zhigou_toolchain.semantic_kernel.packaging.archive import archive_mapping_bytes

from .errors import ServiceBoundaryError
from .modeling_sessions import read
from .projects import get_project, load_catalog, require_access

# Human decisions and independent acceptance are observed, never Agent tools.
SPECIAL_OPERATIONS = {
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


def execute_audited(service, job, request, principal, action):
    role = operation_role(request.operation_id)
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
               "principal_type": principal.principal_type, "review_profile": service.configuration.review_profile}
    audit = StepAudit(audit_root(service, job.project_id, job.job_id, job.attempt), binding,
        content=service.configuration.modeling_audit_content_enabled and principal.can("trace:record") and principal.can("source:read"))
    call_id = audit.before({"kind": "OPERATION", "stage_id": role[0], "actor": role[1],
                            "authority": "OBSERVATION_ONLY", "state": state}, request.parameters)
    token = ACTIVE_AUDIT.set(audit)
    try:
        result = action()
        audit.after(call_id, {"result": result, "computed_state": audit.computed_state}, status="COMMITTED",
                    outcome={"committed_result_sha256": semantic_hash(result)})
        return result
    except BaseException as exc:
        status = "CANCELLED" if service.jobs.get(job.job_id).status in {"CANCELLED", "CANCEL_REQUESTED"} else "FAILED_NOT_COMMITTED"
        # A commit may already exist if the response was lost. Do not invent a rollback.
        if job.job_id in load_catalog(service.root).get("commits", {}):
            status = "COMMIT_REQUIRES_RECONCILIATION"
        if call_id in audit.pending:
            audit.after(call_id, {"computed_state": audit.computed_state}, status=status, error=exc)
        raise
    finally:
        ACTIVE_AUDIT.reset(token)
        audit.close_index()


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
    for index, path in enumerate(paths, 1):
        raw = read_bounded(path)
        size += len(raw)
        require(size <= 64_000_000, "STEP_AUDIT_LIMIT")
        row = json.loads(raw)
        require(row["sequence"] == index and row["previous_event_sha256"] == previous
                and row["event_sha256"] == semantic_hash({k: v for k, v in row.items() if k != "event_sha256"}), "STEP_AUDIT_CHAIN_INVALID")
        bound = row["binding"]
        require(all(bound[k] == getattr(job, k) for k in ("project_id", "job_id", "attempt", "fencing_token", "request_digest", "operation_id")), "STEP_AUDIT_BINDING_INVALID")
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


def audit_index(service, principal, project_id):
    principal = _authorized(service, principal, project_id)
    current = read(get_project(service.root, project_id).root)
    output_status = {o["job_id"]: o["status"] for o in (current or {}).get("outputs", [])}
    records = []
    for job in service.jobs.list_project(project_id):
        role = operation_role(job.operation_id)
        if not role:
            continue
        try:
            service._job(job.job_id, principal)
        except ServiceBoundaryError:
            continue
        for number in range(job.attempt, 0, -1) if job.attempt else [0]:
            attempt = attempt_record(service, job, number)
            root = audit_root(service, project_id, job.job_id, number)
            summary_path = root / "summary.json"
            summary = json.loads(read_bounded(summary_path)) if summary_path.exists() else {}
            records.append({"job_id": job.job_id, "operation_id": job.operation_id, "attempt": number,
                "stage_id": role[0], "actor": role[1], "job_status": attempt.status,
                "stages": summary.get("stages", [role[0]]), "event_count": summary.get("event_count"),
                "content_mode": summary.get("content_mode", "NOT_CONFIRMED"),
                "session_output_status": output_status.get(job.job_id, "NOT_A_CURRENT_SESSION_OUTPUT") if number == job.attempt else "SUPERSEDED_ATTEMPT",
                "availability": "AVAILABLE" if root.exists() and any(root.glob("??????-*.json")) else "ARTIFACT_NOT_AVAILABLE"})
    return {"format": "zhigou-step-audit-index/1.0.0", "records": records,
            "content_capture_enabled": service.configuration.modeling_audit_content_enabled,
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
        tool_starts = [e for e in events if e["phase"] == "BEFORE" and e["metadata"]["kind"] == "TOOL"]
        native = committed.get("agent_execution", {})
        require(len(tool_starts) == len(native.get("records", [])), "STEP_AUDIT_NATIVE_RUN_MISMATCH")
        for event, record in zip(tool_starts, native.get("records", []), strict=True):
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
    files = {f"steps/{e['sequence']:06d}-{e['phase'].lower()}.json": json_bytes(e) for e in events}
    files["journal.jsonl"] = b"".join(json_bytes(e) for e in events)
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
    return archive_mapping_bytes(files)
