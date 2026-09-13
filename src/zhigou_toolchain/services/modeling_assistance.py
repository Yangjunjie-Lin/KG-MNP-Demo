"""LIVE assistance inside the existing staged/fenced proposal job."""
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.contracts.document_io import read_document
from zhigou_toolchain.environment import get_setting
from zhigou_toolchain.modeling.five_stage.agents import invoke
from zhigou_toolchain.modeling.five_stage.assistance import generate, repair
from zhigou_toolchain.modeling.five_stage.compatible import configured_client
from zhigou_toolchain.modeling.five_stage.tools import ModelLock, ToolBlocked

from . import modeling_sessions
from .errors import ServiceBoundaryError
from .requests import ModelAssistance


def repair_findings(report):
    """Pending human review is an enforced workflow state, not a model fix.

    Preserve every actual warning/error, but do not ask a model to clear the
    authority requirement that only the subsequent human review can satisfy.
    """
    return [issue for issue in report.get("issues", []) if issue.get("code") != "HUMAN_REVIEW_REQUIRED"]


def semantic_findings(app, session, project_id):
    output = modeling_sessions.current(session, "modeling.semantic.check")
    if not output:
        return []
    job = app.jobs.get(output["job_id"])
    value = (job.result or {}).get("five_stage") or (job.result or {}).get("automatic_validation", {}).get("five_stage")
    if job.project_id != project_id or job.status != "SUCCEEDED" or not value or semantic_hash(value) != output["digest"]:
        raise ServiceBoundaryError("REPAIR_CHECK_RECEIPT_INVALID", "Repair must read the exact committed semantic-check receipt", status_code=409)
    return [a["content"] for a in value["artifacts"] if a["ref"]["step_id"] in {"4.1", "4.2"}]


def assist(app, modeling, bundle, scope, provider_context, params, *, record_builder=None):
    configuration = ModelAssistance.model_validate(params["model_assistance"]).model_dump()
    session = modeling_sessions.read(modeling.root)
    if not session or session["revision"] != configuration["expected_session_revision"]:
        raise ServiceBoundaryError("SESSION_HEAD_CONFLICT", "LIVE proposals require the current frozen session revision", status_code=409)
    if "manual-candidate-provider" not in params["providers"] or any(p not in {"manual-candidate-provider", "baseline-reuse-provider"} for p in params["providers"]):
        raise ServiceBoundaryError("MODEL_PROVIDER_CONFLICT", "Use the closed manual draft transport and optional baseline provider for LIVE proposals", status_code=422)
    context = {**provider_context, "business_rules": session["frozen"]["business_rules"], "object_families": scope["target_object_families"]}
    # No frozen acceptance answers, expected query rows or repair gold labels.
    context.pop("competency_question_ids", None)
    client = None
    try:
        client = configured_client()
        if configuration["action"] == "REPAIR":
            current = modeling_sessions.current(session, "modeling.proposal")
            if not current or current["identifier"] != configuration["parent_proposal_id"]:
                raise ServiceBoundaryError("REPAIR_PARENT_STALE", "Repair only the current proposal version", status_code=409)
            parent = modeling.find_artifact(current["identifier"])
            directory = modeling.proposal_directory(parent["proposal_id"])
            responses = read_document(directory / "provider-responses.json")
            original = [draft for response in responses for draft in response["candidate_drafts"]]
            if len({d["draft_ref"] for d in original}) != len(original):
                raise ToolBlocked("REPAIR_AMBIGUOUS_DRAFT_REFERENCE")
            report = read_document(directory / "formal-prevalidation-report.json")
            findings = invoke(4, "repair.route", lambda: {"prevalidation": repair_findings(report),
                "semantic_validation": semantic_findings(app, session, modeling.project["project_id"])}, inputs={"parent": parent["proposal_id"]})
            drafts, receipt = invoke(3, "facts.repair", lambda: repair(client, original_drafts=original, context=context, issues=findings,
                configuration=configuration), inputs={"parent": parent["proposal_id"], "findings": findings})
            receipt["parent_proposal_id"] = parent["proposal_id"]
        else:
            locks = {key: ModelLock(get_setting(prefix + "_MODEL", ""), get_setting(prefix + "_REVISION", ""), get_setting(prefix + "_PATH", ""))
                     for key, prefix in (("embedding", "BGE"), ("reranker", "RERANKER"), ("tokenizer", "TOKENIZER"))}
            drafts, receipt = generate(client, context=context, initial_drafts=provider_context.get("manual_drafts", []),
                configuration=configuration, model_locks=locks, record_builder=record_builder)
        return drafts, receipt
    except (ToolBlocked, ImportError, ValueError, KeyError) as exc:
        code = str(exc) if isinstance(exc, ToolBlocked) and str(exc).replace("_", "").isalnum() else type(exc).__name__
        raise ServiceBoundaryError("MODEL_ASSISTANCE_REJECTED", "Model output rejected: " + code, status_code=422) from None
    finally:
        if client:
            client.close()


def recheck(app, project, request, principal, result):
    from .modeling_semantic import execute
    from .models import OperationRequest
    # Publish the new proposal authority only inside this job's staging copy.
    # The outer Worker still fences the entire generation/recheck commit.
    modeling_sessions.after(project.root, request, result)
    candidates = [c for key in ("tbox_candidates", "abox_candidates", "mapping_candidates", "shacl_candidates") for c in result["proposal"][key]]
    checked_request = OperationRequest("modeling.semantic.check", project.project_id,
        {"review_id": result["queue"]["review_queue_id"], "candidate_ids": [c["candidate_id"] for c in candidates]}, idempotency_key=request.idempotency_key)
    try:
        modeling_sessions.before(project.root, checked_request)
        checks = invoke(4, "semantic.check", lambda: execute(app, project, checked_request, principal), inputs=checked_request.parameters)
        modeling_sessions.after(project.root, checked_request, checks)
        return checks
    except ServiceBoundaryError as exc:
        return {"status": "ERROR", "code": exc.code, "approval": "NOT_GRANTED"}
