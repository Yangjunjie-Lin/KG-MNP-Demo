"""Expert versions and bounded loops inside the original session/Worker/CAS."""
from __future__ import annotations

import re
from copy import deepcopy
from datetime import UTC, datetime

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.contracts.document_io import read_document
from zhigou_toolchain.modeling.five_stage.agents import invoke
from zhigou_toolchain.modeling.five_stage.compatible import configured_client
from zhigou_toolchain.modeling.five_stage.expert import (
    ExpertConfiguration,
    default_configuration,
)
from zhigou_toolchain.modeling.five_stage.expert_runtime import (
    ACTIVE_EXPERT,
    ExpertRuntime,
    private_check,
    safe_view,
)
from zhigou_toolchain.modeling.five_stage.tools import ToolBlocked

from . import modeling_sessions
from .errors import ServiceBoundaryError

OPERATIONS = {"modeling.expert.save", "modeling.expert.reaudit"}
COMPUTATIONS = {
    "modeling.profile", "modeling.scope.draft", "modeling.scope", "modeling.prepare", "modeling.cq",
    "modeling.baseline", "modeling.alignment", "modeling.proposal", "modeling.candidate",
    "modeling.semantic.check", "compile.plan.exact", "compile.build", "compile.reproduce",
    "compile.validate", "package.verify", "package.export", "modeling.handoff.check", "modeling.handoff.export",
}


def enabled(session):
    return bool(session and session.get("expert", {}).get("enabled"))


def initial_state():
    return {"enabled": True, "stages": {str(s): default_configuration(s) for s in range(1, 6)},
            "history": [], "loops": []}


def execute(app, project, request, principal):
    session = modeling_sessions.read(project.root)
    params = request.parameters
    if not session or session["revision"] != params["expected_revision"]:
        raise ServiceBoundaryError("SESSION_HEAD_CONFLICT", "Reload current session", status_code=409)
    if request.operation_id == "modeling.expert.reaudit":
        raise ServiceBoundaryError("EXPERT_REAUDIT_REQUIRES_WORKER_CONTEXT", "Use the fenced Worker", status_code=409)
    if principal.principal_type != "HUMAN":
        raise ServiceBoundaryError("HUMAN_CONFIGURATION_REQUIRED", "Only authenticated humans confirm expert guidance", status_code=403)
    configuration = ExpertConfiguration.model_validate(params["configuration"]).model_dump()
    private_check(configuration)
    stage = str(configuration["stage"])
    if not principal.can("scope:approve" if stage == "1" else "review:decide"):
        raise ServiceBoundaryError("FORBIDDEN", "Existing scope/review authority required for expert configuration", status_code=403)
    if not enabled(session):
        session["expert"] = initial_state()
        modeling_sessions.invalidate(session, 1, "Explicit expert-loop upgrade requires new reviews")
    state = session["expert"]
    old = state["stages"][stage]
    if params["expected_configuration_digest"] != old["digest"]:
        raise ServiceBoundaryError("EXPERT_CONFIGURATION_CONFLICT", "Expert configuration changed", status_code=409)
    if params["confirm"] and not configuration["coverage_confirmed"]:
        raise ServiceBoundaryError("EXPERT_CRITERIA_COVERAGE_UNCONFIRMED", "Confirm that criteria cover edited prose", status_code=422)
    from .modeling_scenarios import criterion, effective
    scenario = effective(session)
    if scenario and criterion(scenario, int(stage)) not in configuration["criteria"]:
        raise ServiceBoundaryError("SCENARIO_CRITERION_REQUIRED", "The frozen scene checkpoint cannot be removed or weakened", status_code=422)
    state["history"].append(deepcopy(old))
    version = {"version": old["version"] + 1, "configuration": configuration,
        "status": "CONFIRMED" if params["confirm"] else "DRAFT", "author": principal.principal_id,
        "confirmed_by": principal.principal_id if params["confirm"] else None,
        "confirmed_at": datetime.now(UTC).isoformat() if params["confirm"] else None,
        "origin": "SYNTHETIC_ENGINEERING" if app.configuration.review_profile == "DEVELOPMENT_SINGLE_REVIEWER" else "AUTHENTICATED_HUMAN_CONFIGURATION",
        "project_id": project.project_id, "session_id": session["session_id"]}
    version["digest"] = semantic_hash(version)
    if scenario:
        version["scenario_stage_digest"] = scenario["stage_digests"]["S" + stage]
        version["digest"] = semantic_hash({k: v for k, v in version.items() if k != "digest"})
    state["stages"][stage] = version
    # S1 really invalidates S1, including an already approved scope.
    modeling_sessions.invalidate(session, int(stage), "Expert guidance/review version changed")
    modeling_sessions.save(project.root, session)
    return {"session": session}


def invalidate(session, stage):
    if enabled(session):
        for loop in session["expert"]["loops"]:
            for method in loop.get("methods", []):
                if method["stage_id"] >= stage:
                    method["current"] = False
            loop["current"] = any(m.get("current", True) for m in loop.get("methods", []))


def require_pass(session, operation):
    if not enabled(session):
        return
    name = modeling_sessions.canonical_operation(operation)
    loops = [r for r in session["expert"]["loops"] if r["operation"] == name and r.get("current")]
    if not loops or loops[-1]["decision"] != "PASS":
        raise ServiceBoundaryError("EXPERT_REVIEW_REQUIRED", "Latest artifact requires expert-configured AI review; no human approval is implied", status_code=409)
    output = modeling_sessions.current(session, name)
    if name in modeling_sessions.STAGES and (not output or loops[-1].get("output_digest") != output["digest"]):
        raise ServiceBoundaryError("EXPERT_REVIEW_STALE", "Review is not bound to the current business artifact", status_code=409)
    relevant = {"modeling.proposal": {2, 3}, "modeling.prepare": {2}, "modeling.semantic.check": {4},
                "modeling.scope": {1}, "compile.plan.exact": {5}, "compile.build": {5}}.get(name, set(range(1, 6)))
    selected = [m for m in loops[-1]["methods"] if m["stage_id"] in relevant]
    if not selected or any(not m.get("current", True) for m in selected):
        raise ServiceBoundaryError("EXPERT_REVIEW_STALE", "Affected method review is stale", status_code=409)
    for method in selected:
        from .modeling_scenarios import require_confirmation
        require_confirmation(session, method["stage_id"])
        if method["configuration_digest"] != session["expert"]["stages"][str(method["stage_id"])]["digest"]:
            raise ServiceBoundaryError("EXPERT_REVIEW_STALE", "Review conditions changed", status_code=409)


def require_package(session, package_id, *, export_result=None):
    """Exact business target, including original direct-download endpoints."""
    if not enabled(session):
        return
    built = modeling_sessions.current(session, "compile.build")
    if not built or built["identifier"] != package_id:
        raise ServiceBoundaryError("EXPERT_PACKAGE_STALE", "Selected package is not the current reviewed package", status_code=409)
    require_pass(session, "compile.build")
    if export_result is not None:
        report = export_result.get("expert_loop", {})
        if report.get("decision") != "PASS" or report.get("configuration_digests", {}).get("5") != session["expert"]["stages"]["5"]["digest"]:
            raise ServiceBoundaryError("EXPERT_EXPORT_REVIEW_STALE", "Export package review is missing or uses outdated conditions", status_code=409)


def before(session, request):
    from .modeling_scenarios import require_active
    scenario_execution = request.operation_id.startswith(("modeling.", "compile.", "review.")) or request.operation_id in {"package.export", "package.verify", "registry.import"}
    if scenario_execution and request.operation_id not in {"modeling.scenario.preview", "modeling.scenario.save", "modeling.session.open"}:
        require_active(session)
    if not enabled(session):
        return
    if request.operation_id in {"package.export", "package.verify", "compile.validate", "registry.import", "modeling.handoff.check", "modeling.handoff.export"}:
        require_package(session, request.parameters["package_id"])
    if request.operation_id == "compile.reproduce":
        planned = modeling_sessions.current(session, "compile.plan.exact")
        if not planned or planned["identifier"] != request.parameters["plan_id"]:
            raise ServiceBoundaryError("EXPERT_PLAN_STALE", "Selected plan is not current", status_code=409)
    if request.operation_id in {"modeling.scope", "modeling.scope.approve"}:
        input_reviews = [r for r in session["expert"]["loops"] if r.get("current") and r["operation"] in {"modeling.profile", "modeling.scope.draft"}
                         and r["decision"] == "PASS" and {"1.1", "1.2"}.issubset({m["method_id"] for m in r["methods"] if m.get("current", True)})]
        if not input_reviews:
            raise ServiceBoundaryError("EXPERT_INPUT_REVIEW_REQUIRED", "Run/review input checks and profiling under confirmed guidance before scope creation", status_code=409)
    upstream = {
        "modeling.scope.approve": ["modeling.scope"], "modeling.prepare": ["modeling.scope"],
        "modeling.proposal": ["modeling.prepare"], "review.action": ["modeling.proposal", "modeling.semantic.check"],
        "review.finalize": ["modeling.proposal", "modeling.semantic.check"],
        "compile.plan.exact": ["modeling.proposal", "modeling.semantic.check"],
        "compile.build": ["compile.plan.exact"], "compile.reproduce": ["compile.plan.exact"],
        "package.export": ["compile.build"], "modeling.handoff.check": ["compile.build"],
        "modeling.handoff.export": ["compile.build"], "registry.import": ["compile.build"],
    }
    for op in upstream.get(modeling_sessions.canonical_operation(request.operation_id), []):
        require_pass(session, op)


def sources_for(project, session):
    from .sources import verified_run
    data = verified_run(project.root, session["frozen"]["run_id"]).dataset
    sources = {"rule:" + str(i): {"text": text, "origin": "FROZEN_BUSINESS_RULE"}
               for i, text in enumerate(session["frozen"]["business_rules"])}
    for item in data["items"]:
        payload = item["payload"]
        text = payload.get("text") if item["item_kind"] == "text-block" else payload.get("value", {}).get("normalized_lexical_value")
        if isinstance(text, str) and text:
            sources[item["item_id"]] = {"text": text, "evidence_refs": item["evidence_refs"], "item_kind": item["item_kind"]}
    private_check(sources)
    return sources


def patch_targets(request, result, modeling):
    name = modeling_sessions.canonical_operation(request.operation_id)
    if name == "modeling.scope":
        scope = result["scope"]
        return {"scope": {"description": scope["domain_description"], "in_scope": scope["in_scope"], "out_of_scope": scope["out_of_scope"]}}
    if name == "modeling.scope.draft":
        draft = next(a["content"]["proposal"] for a in result["five_stage"]["artifacts"] if a["ref"]["step_id"] == "1.3")
        return {"scope": draft}
    if name == "compile.plan.exact":
        return {"plan": {"package_name": request.parameters["package_name"]}}
    if name in {"modeling.proposal", "modeling.semantic.check"}:
        proposal_id = result.get("expert_routed_proposal", result.get("proposal", {})).get("proposal_id")
        if not proposal_id:
            proposal_id = modeling.find_artifact(request.parameters["review_id"])["proposal_id"]
        responses = read_document(modeling.proposal_directory(proposal_id) / "provider-responses.json")
        drafts = [d for r in responses for d in r["candidate_drafts"]]
        if len({d["draft_ref"] for d in drafts}) != len(drafts):
            raise ToolBlocked("EXPERT_AMBIGUOUS_DRAFT_REFERENCE")
        return {d["draft_ref"]: d for d in drafts}
    raise ToolBlocked("EXPERT_ROUTE_TO_EARLIER_STAGE_OR_HUMAN")


def validate_patch(targets, patch, issues, sources, operation, *, allowed_iris=()):
    """No generic JSON Patch. Source bytes, identities, SHACL and answers immutable."""
    changed, revised, seen = [], deepcopy(targets), set()
    issues_by_id = {i["issue_id"]: i for i in issues}
    subjects = {d.get("body", {}).get("subject_iri") for d in targets.values()
                if d.get("body", {}).get("candidate_type") == "INDIVIDUAL"}
    for p in patch["changes"]:
        issue = issues_by_id.get(p["issue_id"])
        source = sources.get(p["evidence_ref"])
        key = (p["target"], p["field"])
        if (not issue or key in seen or p["target"] not in targets or not source
                or p["evidence_ref"] not in issue["evidence_refs"]):
            raise ToolBlocked("EXPERT_PATCH_REFERENCE_FORBIDDEN")
        seen.add(key)
        location = issue.get("location", "")
        allowed_locations = {"literal": {"body.literal", "body.literal.lexical_value"}, "label": {"body.label"},
            "object_iri": {"body.object_iri"}, "description": {"description", "domain_description"}}.get(p["field"], {p["field"]})
        exact_locations = {p["target"] + "." + field for field in allowed_locations} | {
            "/" + p["target"] + "/" + field.replace(".", "/") for field in allowed_locations}
        if location not in exact_locations:
            raise ToolBlocked("EXPERT_PATCH_ISSUE_LOCATION_MISMATCH")
        if source["text"][p["quote_start"]:p["quote_start"] + len(p["quote"])] != p["quote"]:
            raise ToolBlocked("EXPERT_PATCH_QUOTE_INVALID")
        target = revised[p["target"]]
        before = deepcopy(target)
        field, value = p["field"], p["value"]
        if operation in {"modeling.scope", "modeling.scope.draft"}:
            permitted = {"description", "in_scope", "out_of_scope"} if operation == "modeling.scope" else {"objects", "targets", "exclusions"}
            if field not in permitted or issue["target_stage"] != 1:
                raise ToolBlocked("EXPERT_PATCH_SCOPE_FORBIDDEN")
            if (field == "description" and not isinstance(value, str)) or (field != "description" and not isinstance(value, list)):
                raise ToolBlocked("EXPERT_PATCH_VALUE_INVALID")
            target[field] = value
        elif operation == "compile.plan.exact":
            if field != "package_name" or not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,100}", value) or issue["target_stage"] != 5:
                raise ToolBlocked("EXPERT_PATCH_FINAL_ARTIFACT_FORBIDDEN")
            target[field] = value
        elif operation == "modeling.proposal":
            body, kind = target["body"], target["draft_kind"]
            if not isinstance(value, str):
                raise ToolBlocked("EXPERT_PATCH_VALUE_INVALID")
            if kind == "ABOX" and issue["target_stage"] == 3:
                if p["evidence_ref"] not in target["kg_ir_item_refs"]:
                    raise ToolBlocked("EXPERT_PATCH_UNBOUND_SOURCE")
                if field == "literal" and body["candidate_type"] == "DATA_PROPERTY_ASSERTION" and value and value in p["quote"]:
                    body["literal"]["lexical_value"] = value
                elif field == "object_iri" and body["candidate_type"] == "OBJECT_PROPERTY_ASSERTION" and value in subjects and value in p["quote"]:
                    body["object_iri"] = value
                else:
                    raise ToolBlocked("EXPERT_PATCH_FACT_NOT_GROUNDED")
            elif (kind == "TBOX" and target["candidate_action"] != "REUSE_EXISTING" and issue["target_stage"] == 2
                    and field == "label" and value and value in p["quote"]):
                # Labels only; existing hard axioms and external baseline never change.
                body["label"] = value
            elif (kind == "TBOX" and issue["target_stage"] == 2 and field == "object_iri"
                    and body["candidate_type"] in {"SUBCLASS_AXIOM", "DOMAIN_AXIOM", "RANGE_AXIOM"}
                    and value in allowed_iris and value in p["quote"] and p["evidence_ref"].startswith("rule:")):
                body["object_iri"] = value
            else:
                raise ToolBlocked("EXPERT_PATCH_STRUCTURE_OR_RULE_FORBIDDEN")
        else:
            raise ToolBlocked("EXPERT_PATCH_OPERATION_FORBIDDEN")
        if before == target:
            raise ToolBlocked("EXPERT_PATCH_NO_CHANGE")
        changed.append({"target": p["target"], "field": field, "before": before, "after": deepcopy(target),
                        "issue_id": p["issue_id"], "evidence_ref": p["evidence_ref"]})
    if not changed:
        raise ToolBlocked("EXPERT_PATCH_NO_CHANGE")
    return {"targets": revised, "changes": changed}


def allowed_patch_view(targets):
    """A permission projection, not a list falsely suggesting all drafts can change."""
    view = {}
    for identifier, target in targets.items():
        if "draft_kind" not in target:
            view[identifier] = {k: v for k, v in target.items() if k in {
                "description", "in_scope", "out_of_scope", "objects", "targets", "exclusions", "package_name"}}
            continue
        kind, body = target["draft_kind"], target["body"]
        fields = {}
        if kind == "ABOX":
            if body["candidate_type"] == "DATA_PROPERTY_ASSERTION":
                fields["literal"] = {"location": identifier + ".body.literal.lexical_value", "value": body["literal"]["lexical_value"]}
            elif body["candidate_type"] == "OBJECT_PROPERTY_ASSERTION":
                fields["object_iri"] = {"location": identifier + ".body.object_iri", "value": body["object_iri"]}
        elif kind == "TBOX" and target["candidate_action"] != "REUSE_EXISTING":
            fields["label"] = {"location": identifier + ".body.label", "value": body.get("label")}
            if body["candidate_type"] in {"SUBCLASS_AXIOM", "DOMAIN_AXIOM", "RANGE_AXIOM"}:
                fields["object_iri"] = {"location": identifier + ".body.object_iri", "value": body.get("object_iri"),
                    "restriction": "Locked baseline endpoint and explicit frozen rule quote required"}
        if fields:
            view[identifier] = {"editable_fields": fields, "source_item_refs": target["kg_ir_item_refs"],
                                "evidence_refs": target["evidence_refs"]}
    return {"targets": view, "policy": "All unspecified objects and fields are immutable. Exact issue location and original source quote are mandatory."}


def metadata_report(report):
    """Full opinions/diffs remain in the authorized original StepAudit channel."""
    result = {k: deepcopy(v) for k, v in report.items() if k != "rounds"}
    result["rounds"] = []
    for row in report["rounds"]:
        methods = []
        for method in row["methods"]:
            methods.append({k: deepcopy(v) for k, v in method.items() if k != "review"})
            methods[-1]["review_digest"] = semantic_hash(method["review"])
            methods[-1]["issues"] = [{k: i[k] for k in ("issue_id", "criterion_id", "severity", "target_stage", "evidence_refs")}
                                      for i in method["review"]["issues"]]
        result["rounds"].append({k: deepcopy(v) for k, v in row.items() if k not in {"methods", "patch", "changes"}} | {
            "methods": methods, "changes": [{"target": c["target"], "field": c["field"],
                "before_digest": semantic_hash(c["before"]), "after_digest": semantic_hash(c["after"])} for c in row.get("changes", [])]})
    return result


def coordinate(app, project, request, principal, job, original):
    from zhigou_toolchain.modeling.control_plane.service import ModelingWorkspaceService

    from .authorization_policy import authorize
    from .models import OperationRequest
    from .projects import get_project, require_access
    from .requests import validate_parameters

    session = modeling_sessions.read(project.root)
    if request.operation_id == "modeling.expert.reaudit":
        return reaudit(app, project, request, principal, job)
    if not enabled(session) or request.operation_id not in COMPUTATIONS:
        return original()
    assert session is not None
    versions = session["expert"]["stages"]
    sources = sources_for(project, session)
    modeling = ModelingWorkspaceService(project.root)
    def guard():
        current = app.tokens.resolve(principal.token_id)
        authorize(current, app.catalog[request.operation_id], request)
        require_access(current, get_project(app.root, project.project_id))
        if not current.can("model:propose") or not current.can("source:read"):
            raise ServiceBoundaryError("EXPERT_MODEL_PERMISSION_REQUIRED", "Model and source-read grants are required", status_code=403)
        app.jobs.require_lease(job)
        if get_project(app.root, project.project_id).authority_revision != project.authority_revision - 1:
            raise ServiceBoundaryError("AUTHORITY_CONFLICT", "Input, configuration or authority changed during expert loop", status_code=409)
    from .modeling_scenarios import effective
    runtime = ExpertRuntime(versions, guard=guard, sources=sources, client_factory=configured_client, scenario=effective(session))
    name = modeling_sessions.canonical_operation(request.operation_id)
    plan_request = None
    if name == "compile.build":
        plan_output = modeling_sessions.current(session, "compile.plan.exact")
        if plan_output and plan_output["identifier"] == request.parameters["plan_id"]:
            from .execution import committed_result
            plan_job = app.jobs.get(plan_output["job_id"])
            committed_result(app, plan_job)
            if plan_job.project_id == project.project_id and plan_job.operation_id == "compile.plan.exact":
                plan_request = {k: v for k, v in app.jobs.parameters(plan_job.job_id).items() if k != "__principal"}
    def produce(patch):
        if patch is None:
            return original()
        if name == "modeling.scope.draft":
            from .modeling_five_stage import execute
            return invoke(1, "scope.suggest", lambda: execute(app, project, request, principal,
                expert_draft=patch["targets"]["scope"]), inputs={"patch": patch, "original_parameters": request.parameters})
        if name == "compile.build" and plan_request is not None:
            from .compilation import execute as handler
            params = {**plan_request, **patch["targets"]["plan"]}
            plan_op = OperationRequest("compile.plan.exact", project.project_id, params, idempotency_key=request.idempotency_key)
            validate_parameters(plan_op)
            modeling_sessions.before(project.root, plan_op)
            planned = invoke(5, "compile.plan", lambda: handler(app, project, plan_op, principal), inputs=safe_view(params))
            modeling_sessions.after(project.root, plan_op, planned)
            build_op = OperationRequest("compile.build", project.project_id, {"plan_id": planned["plan"]["plan_id"]}, idempotency_key=request.idempotency_key)
            built = invoke(5, "compile.build", lambda: handler(app, project, build_op, principal), inputs=build_op.parameters)
            return {**built, "plan": planned["plan"], "expert_routed_plan": planned["plan"]["plan_id"]}
        if name in {"modeling.proposal", "modeling.semantic.check"}:
            from .modeling import _propose
            params = request.parameters
            if name == "modeling.semantic.check":
                queue = modeling.find_artifact(params["review_id"])
                parent = modeling.find_artifact(queue["proposal_id"])
                mapping = read_document(modeling.proposal_directory(parent["proposal_id"]) / "record-mapping-proposal.json")
                params = {"bundle_id": parent["modeling_input_bundle_id"], "providers": ["manual-candidate-provider"]}
                if mapping["mapping"]:
                    params["record_mapping"] = mapping["mapping"]
            result = _propose(app, modeling, params, expert_drafts=list(patch["targets"].values()))
            from .modeling_assistance import recheck
            proposal_request = OperationRequest("modeling.proposal", project.project_id, params, idempotency_key=request.idempotency_key)
            result["automatic_validation"] = recheck(app, project, proposal_request, principal, result)
            if name == "modeling.semantic.check":
                return {**result, **result["automatic_validation"], "expert_routed_proposal": result["proposal"],
                        "expert_routed_review_id": result["queue"]["review_queue_id"],
                        "human_approval": "NEW_REVIEW_REQUIRED"}
            return result
        params = {**request.parameters, **patch["targets"]["scope" if name == "modeling.scope" else "plan"]}
        changed_request = OperationRequest(name, project.project_id, params, idempotency_key=request.idempotency_key)
        validate_parameters(changed_request)
        if name == "modeling.scope":
            from .modeling import execute as handler
            return invoke(1, "scope.validate", lambda: handler(app, project, changed_request, principal), inputs=params)
        from .compilation import execute as handler
        return invoke(5, "compile.plan", lambda: handler(app, project, changed_request, principal), inputs=safe_view(params))
    def revise(result, patch, issues, digest):
        targets = {"plan": {"package_name": plan_request["package_name"]}} if name == "compile.build" and plan_request else patch_targets(request, result, modeling)
        if patch is None:
            return allowed_patch_view(targets)
        allowed_iris = set()
        if name in {"modeling.proposal", "modeling.semantic.check"}:
            proposal = result.get("proposal") or result.get("expert_routed_proposal")
            if not proposal:
                proposal = modeling.find_artifact(modeling.find_artifact(request.parameters["review_id"])["proposal_id"])
            allowed_iris = {e["iri"] for e in modeling.find_artifact(proposal["baseline_snapshot_id"])["elements"]}
        validated = validate_patch(targets, patch, issues, sources,
            "modeling.proposal" if name == "modeling.semantic.check" else "compile.plan.exact" if name == "compile.build" else name, allowed_iris=allowed_iris)
        if name == "compile.build" and plan_request is not None:
            plan_request["package_name"] = validated["targets"]["plan"]["package_name"]
        # Original controlled content channel, not an AI-authored reviews/*.jsonl.
        from zhigou_toolchain.modeling.five_stage.audit import ACTIVE_AUDIT
        audit = ACTIVE_AUDIT.get()
        if audit:
            cid = audit.before({"kind": "EXPERT_PATCH", "loop_id": runtime.loop_id,
                "revision_round": runtime.round, "base_digest": digest}, patch)
            audit.after(cid, validated, status="VALIDATED_NOT_YET_APPLIED")
        return validated
    token = ACTIVE_EXPERT.set(runtime)
    try:
        from zhigou_toolchain.modeling.five_stage.scenario_outputs import (
            project_operation,
        )
        result, report = runtime.run(lambda patch: project_operation(runtime.scenario, request.operation_id, produce(patch)), revise)
    finally:
        ACTIVE_EXPERT.reset(token)
    if result is None:
        raise ServiceBoundaryError(report["stop_reason"] or "EXPERT_BLOCKED", "Expert loop did not produce a candidate; consult authorized audit", status_code=409)
    guard()
    result["expert_loop"] = metadata_report(report)
    if result.get("expert_routed_proposal"):
        result["expert_loop"]["routed_proposal"] = result["expert_routed_proposal"]["proposal_id"]
    if result.get("expert_routed_plan"):
        result["expert_loop"]["routed_plan"] = result["expert_routed_plan"]
    # Persist after() publishes the matching business outputs; no parallel store.
    return result


def reaudit(app, project, request, principal, job):
    """Review the exact committed candidate; never regenerate on a review click."""
    import json

    from zhigou_toolchain.modeling.delivery.exchange_io import read_archive

    from .execution import committed_result
    from .modeling_audit import download_audit
    from .projects import get_project

    session = modeling_sessions.read(project.root)
    params = request.parameters
    if session is None or not enabled(session) or session["revision"] != params["expected_revision"]:
        raise ServiceBoundaryError("SESSION_HEAD_CONFLICT", "Reload current expert session", status_code=409)
    assert session is not None
    prior = app._job(params["job_id"], principal)
    value = committed_result(app, prior)
    if prior.project_id != project.project_id or not value or prior.operation_id not in COMPUTATIONS:
        raise ServiceBoundaryError("EXPERT_REVIEW_TARGET_INVALID", "Select a committed computational job in this project", status_code=409)
    from .projects import load_catalog
    prior_session = modeling_sessions.read(load_catalog(app.root)["commits"][prior.job_id]["root"])
    if not prior_session or prior_session["frozen"] != session["frozen"]:
        raise ServiceBoundaryError("EXPERT_REVIEW_INPUT_CHANGED", "Frozen input changed since this candidate", status_code=409)
    from .modeling_scenarios import effective
    if effective(prior_session) != effective(session):
        raise ServiceBoundaryError("SCENARIO_REGENERATION_REQUIRED", "Scene configuration changed; generate the corresponding view/version before re-review", status_code=409)
    business = {k: v for k, v in value.items() if k not in {"expert_loop", "agent_execution", "step_audit_anchor"}}
    if semantic_hash(safe_view(business)) != params["candidate_digest"]:
        raise ServiceBoundaryError("EXPERT_REVIEW_TARGET_CHANGED", "Candidate digest changed", status_code=409)
    entry = next((o for o in reversed(session["outputs"]) if o["operation"] == modeling_sessions.canonical_operation(prior.operation_id)), None)
    if entry and entry["job_id"] != prior.job_id:
        raise ServiceBoundaryError("EXPERT_REVIEW_TARGET_STALE", "A newer candidate exists", status_code=409)
    # A pre-guidance edit requires regeneration, not only re-review.
    old_loop = next((r for r in session["expert"]["loops"] if r["job_id"] == prior.job_id), None)
    if old_loop is None:
        raise ServiceBoundaryError("EXPERT_REGENERATION_REQUIRED", "Legacy generation has no frozen expert guidance; do not invent it", status_code=409)
    if old_loop:
        for method in old_loop["methods"]:
            old = next((v for v in [*session["expert"]["history"], *session["expert"]["stages"].values()]
                        if v["digest"] == method["configuration_digest"]), None)
            new = session["expert"]["stages"][str(method["stage_id"])]
            if not old or old["configuration"]["pre_guidance_prompt"] != new["configuration"]["pre_guidance_prompt"]:
                raise ServiceBoundaryError("EXPERT_REGENERATION_REQUIRED", "Pre-guidance changed; regenerate through original operation", status_code=409)
            method_id = method["method_id"]
            if old["configuration"]["method_overrides"].get(method_id, {}).get("pre_guidance_prompt") != new["configuration"]["method_overrides"].get(method_id, {}).get("pre_guidance_prompt"):
                raise ServiceBoundaryError("EXPERT_REGENERATION_REQUIRED", "Method pre-guidance changed", status_code=409)
    feedback = []
    if params.get("feedback"):
        if principal.principal_type != "HUMAN" or not principal.can("review:decide"):
            raise ServiceBoundaryError("HUMAN_FEEDBACK_REQUIRED", "Feedback requires authenticated reviewer", status_code=403)
        private_check(params["feedback"])
        feedback = [{"actor": "HUMAN", "author": principal.principal_id, "candidate_digest": params["candidate_digest"],
            "text": params["feedback"], "timestamp": datetime.now(UTC).isoformat(),
            "origin": "SYNTHETIC_ENGINEERING" if app.configuration.review_profile == "DEVELOPMENT_SINGLE_REVIEWER" else "AUTHENTICATED_HUMAN"}]
    def guard():
        current = app.tokens.resolve(principal.token_id)
        if not all(current.can(p) for p in ("model:propose", "source:read", "source:export", "package:read", "trace:export")):
            raise ServiceBoundaryError("FORBIDDEN", "Re-review permissions revoked", status_code=403)
        app._job(prior.job_id, current)
        app.jobs.require_lease(job)
        if get_project(app.root, project.project_id).authority_revision != project.authority_revision - 1:
            raise ServiceBoundaryError("AUTHORITY_CONFLICT", "Expert review target changed", status_code=409)
    archive = read_archive(download_audit(app, principal, project.project_id, prior.job_id))
    events = [json.loads(line) for line in archive["journal.jsonl"].splitlines()]
    last_round = value.get("expert_loop", {}).get("revision_round")
    starts = {e["call_id"]: e for e in events if e["phase"] == "BEFORE"}
    runtime = ExpertRuntime(session["expert"]["stages"], guard=guard, sources=sources_for(project, session),
                            client_factory=configured_client, feedback=feedback, scenario=session.get("scenario", {}).get("effective"))
    def produce(_patch):
        for event in events:
            meta = event["metadata"]
            if (event["phase"] != "AFTER" or meta["kind"] != "TOOL" or not meta.get("method_id")
                    or meta.get("tool_id", "").startswith("expert.")):
                continue
            if meta.get("expert_binding", {}).get("revision_round") != last_round:
                continue
            start = starts[event["call_id"]]
            if (meta.get("status") != "SUCCEEDED" or start["payload"].get("capture") != "CAPTURED"
                    or event["payload"].get("capture") != "CAPTURED"):
                raise ToolBlocked("EXPERT_REVIEW_CONTENT_UNAVAILABLE")
            runtime.observe({**meta, "audit_call_id": event["call_id"]}, start["payload"]["value"], event["payload"]["value"])
        return deepcopy(business)
    def no_patch(*_):
        raise ToolBlocked("EXPERT_REVIEW_REQUIRES_NEW_COMPUTATION")
    token = ACTIVE_EXPERT.set(runtime)
    try:
        _, report = runtime.run(produce, no_patch)
    finally:
        ACTIVE_EXPERT.reset(token)
    guard()
    summary = metadata_report(report)
    summary["reviewed_operation"] = modeling_sessions.canonical_operation(prior.operation_id)
    summary["reviewed_job_id"] = prior.job_id
    if entry and report["decision"] == "PASS":
        entry["status"] = "CURRENT"
        entry.pop("stale_reason", None)
        modeling_sessions.save(project.root, session)
    return {"expert_loop": summary}


def after(session, request, result):
    if not enabled(session) or "expert_loop" not in result:
        return
    report = result["expert_loop"]
    name = report.get("reviewed_operation", modeling_sessions.canonical_operation(request.operation_id))
    for old in session["expert"]["loops"]:
        if old["operation"] == name:
            old["current"] = False
            for method in old["methods"]:
                method["current"] = False
    methods = [dict(m, stage_id=int(m["method_id"][0]), current=True) for m in report["rounds"][-1]["methods"]] if report["rounds"] else []
    session["expert"]["loops"].append({"operation": name, "job_id": request.idempotency_key,
        "current": True, "methods": methods, "output_digest": (modeling_sessions.current(session, name) or {}).get("digest"), **report})
    if report.get("routed_proposal"):
        # The same staged operation really generated and reviewed the new S2/S3
        # candidate before re-running S4. It is not a copied old PASS.
        proposal_output = modeling_sessions.current(session, "modeling.proposal")
        if not proposal_output:
            raise ServiceBoundaryError("EXPERT_ROUTED_OUTPUT_MISSING", "Routed proposal was not saved in the original session", status_code=409)
        session["expert"]["loops"].append({"operation": "modeling.proposal", "job_id": request.idempotency_key,
            "current": True, "methods": deepcopy(methods), "output_digest": proposal_output["digest"], **report})
    if report.get("routed_plan"):
        plan_output = modeling_sessions.current(session, "compile.plan.exact")
        if not plan_output:
            raise ServiceBoundaryError("EXPERT_ROUTED_OUTPUT_MISSING", "Routed plan was not saved in the original session", status_code=409)
        session["expert"]["loops"].append({"operation": "compile.plan.exact", "job_id": request.idempotency_key,
            "current": True, "methods": deepcopy(methods), "output_digest": plan_output["digest"], **report})
    session["revision"] += 1
