"""Five-stage authority carried by the existing copy-on-write project commit.

Legacy workspaces remain readable. Opening a session opts the project into
strict run/selection/check binding; closing a browser never closes authority.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn
from zhigou_toolchain.contracts.document_io import atomic_write_json as write_document
from zhigou_toolchain.contracts.document_io import read_document

from .errors import ServiceBoundaryError

OPERATIONS = frozenset({"modeling.session.open", "modeling.session.revise"})
REQUIRED = ("integrity", "explicit_target_coverage", "shacl", "owl_profile", "hermit")
STAGES = {
    "modeling.scope": (1, "scope", "scope_id"),
    "modeling.scope.approve": (1, "approval", "approval_id"),
    "modeling.prepare": (2, "bundle", "modeling_input_bundle_id"),
    "modeling.proposal": (3, "proposal", "proposal_id"),
    "modeling.semantic.check": (4, "five_stage", "session_id"),
    "review.finalize": (4, "confirmed_package", "package_id"),
    "compile.plan": (5, "plan", "plan_id"),
    "compile.plan.exact": (5, "plan", "plan_id"),
    "compile.build": (5, "manifest", "package_id"),
}


def read(root):
    path = Path(root) / "registry" / "modeling-session.json"
    return read_document(path, max_bytes=16 * 1024 * 1024) if path.exists() else None


def save(root, session):
    (Path(root) / "registry").mkdir(parents=True, exist_ok=True)
    write_document(Path(root) / "registry" / "modeling-session.json", session)


def invalidate(session, stage, reason):
    for item in session["outputs"]:
        if item["stage"] >= stage and item["status"] != "STALE":
            item.update(status="STALE", stale_reason=reason)
    session["checks"] = []
    session["revision"] += 1
    session["events"].append({"revision": session["revision"], "from_stage": stage, "reason": reason})


def execute(app, project, request, principal):
    from .sources import verified_run
    params = request.parameters
    previous = read(project.root)
    expected = params.get("expected_revision")
    if expected != (previous["revision"] if previous else None):
        raise ServiceBoundaryError("SESSION_HEAD_CONFLICT", "Reload the modeling session before changing dependencies", status_code=409)
    if request.operation_id == "modeling.session.open":
        verified = verified_run(project.root, params["run_id"])
        from zhigou_toolchain.modeling.five_stage.profiling import check_input
        quality = check_input(verified.dataset, verified.quality_report)
        if quality["quarantined"] or not quality["usable"]:
            raise ServiceBoundaryError("INPUT_QUALITY_REVIEW_REQUIRED", "Repair quarantined or empty input before freezing a strict session", status_code=422)
        frozen = {"run_id": params["run_id"], "dataset_digest": semantic_hash(verified.dataset),
                  "business_rules": params["business_rules"], "acceptance": params["acceptance"],
                  "configuration": params.get("configuration", {}), "quality_digest": semantic_hash(quality)}
        identifier = stable_urn("modeling-session", {"project": project.project_id, "frozen": frozen})
        if previous and previous["session_id"] == identifier:
            return {"session": previous}
        session = {"schema_version": "1.0.0", "session_id": identifier, "project_id": project.project_id,
                   "revision": (previous["revision"] + 1) if previous else 1, "frozen": frozen,
                   "required_checks": list(REQUIRED), "outputs": [], "checks": [], "events": [],
                   "execution_mode": "DETERMINISTIC", "opened_by": principal.principal_id}
        if previous:
            history = deepcopy(previous)
            invalidate(history, 1, "New input/rules/acceptance/configuration session")
            (Path(project.root) / "registry" / "modeling-session-history").mkdir(exist_ok=True)
            write_document(Path(project.root) / "registry" / "modeling-session-history" / f"{semantic_hash(previous)}.json", history)
    else:
        if not previous:
            raise ServiceBoundaryError("SESSION_REQUIRED", "Open a modeling session first", status_code=409)
        session = previous
        revised = params["configuration"]
        if revised == session["frozen"]["configuration"]:
            return {"session": session}
        invalidate(session, 2, "Tool/model/mapping configuration changed")
        session["frozen"]["configuration"] = revised
    save(project.root, session)
    return {"session": session}


def current(session, operation):
    return next((o for o in reversed(session["outputs"]) if o["operation"] == operation and o["status"] != "STALE"), None)


def before(root, request):
    session = read(root)
    if not session or request.operation_id in OPERATIONS:
        return
    name, params = canonical_operation(request.operation_id), request.parameters
    if name in {"modeling.scope", "modeling.profile", "modeling.scope.draft"} and params["run_id"] != session["frozen"]["run_id"]:
        raise ServiceBoundaryError("SESSION_INPUT_STALE", "Open a new session for changed input", status_code=409)
    bindings = {
        "modeling.scope.approve": ("modeling.scope", "scope_id"),
        "modeling.prepare": ("modeling.scope", "scope_id"),
        "modeling.proposal": ("modeling.prepare", "bundle_id"),
        "compile.plan": ("review.finalize", "confirmed_package_id"),
        "compile.plan.exact": ("review.finalize", "confirmed_package_id"),
    }
    if name in bindings:
        upstream, key = bindings[name]
        output = current(session, upstream)
        if not output or params[key] != output["identifier"]:
            raise ServiceBoundaryError("SESSION_DEPENDENCY_STALE", "Selected upstream artifact is not current", status_code=409)
    if name == "modeling.prepare":
        approval = current(session, "modeling.scope.approve")
        if not approval or params["approval_id"] != approval["identifier"]:
            raise ServiceBoundaryError("SESSION_APPROVAL_STALE", "Scope approval is not the current session approval", status_code=409)
    if name == "compile.plan":
        raise ServiceBoundaryError("FROZEN_EXACT_ANSWERS_REQUIRED", "Strict sessions compile against stage-one frozen exact answers", status_code=409)
    if name == "compile.plan.exact":
        provided = [{"query_asset_id": o["query_asset_id"], "expected": o["expected"]} for o in params["oracles"]]
        if semantic_hash(provided) != semantic_hash(session["frozen"]["acceptance"]):
            raise ServiceBoundaryError("ACCEPTANCE_BASELINE_CHANGED", "Final answers must match the independently frozen input acceptance", status_code=409)
    if name == "compile.build":
        plans = [current(session, op) for op in ("compile.plan", "compile.plan.exact")]
        if not any(p and p["identifier"] == params["plan_id"] for p in plans):
            raise ServiceBoundaryError("SESSION_DEPENDENCY_STALE", "Compilation plan is stale", status_code=409)
    if name in {"review.action", "review.finalize", "modeling.semantic.check"}:
        proposal = current(session, "modeling.proposal")
        if not proposal or params["review_id"] != proposal["review_id"]:
            raise ServiceBoundaryError("SESSION_REVIEW_STALE", "Review belongs to an outdated proposal", status_code=409)
        if params.get("decision") == "MODIFY_AND_ACCEPT":
            raise ServiceBoundaryError("REPAIR_REVIEW_REQUIRED", "Repair the mapping and submit a new proposal, then recheck and review", status_code=409)


def after(root, request, result):
    session = read(root)
    operation = canonical_operation(request.operation_id)
    if session and operation == "review.action":
        for output in session["outputs"]:
            if output["operation"] == "review.finalize" or output["stage"] == 5:
                output.update(status="STALE", stale_reason="Review head changed after freezing")
        # New human decisions do not invalidate checks on unchanged facts, but
        # always invalidate a previously frozen approval/compilation snapshot.
        session["revision"] += 1
        session["events"].append({"revision": session["revision"], "reason": "Review head changed",
                                  "review_head": result["action"]["action_hash"]})
        save(root, session)
        return
    if not session or operation not in STAGES:
        return
    stage, key, id_key = STAGES[operation]
    content = result.get(key, {})
    previous = current(session, operation)
    digest = semantic_hash(content)
    if previous and previous["digest"] != digest:
        invalidate(session, stage, f"{request.operation_id} produced a new dependency version")
    entry = {"stage": stage, "operation": operation, "identifier": content.get(id_key),
             "digest": digest, "status": "CURRENT", "job_id": request.idempotency_key,
             "dependency_digest": semantic_hash(session["frozen"])}
    if operation == "modeling.proposal":
        entry["review_id"] = result["queue"]["review_queue_id"]
    if not previous or previous["digest"] != digest:
        session["outputs"].append(entry)
        session["revision"] += 1
    if request.operation_id == "modeling.semantic.check":
        artifacts = content["artifacts"]
        source = next(a["content"] for a in artifacts if a["ref"]["step_id"] == "3.6")
        integrity = next(a["content"] for a in artifacts if a["ref"]["step_id"] == "4.1")
        graph = next((a["content"] for a in artifacts if a["ref"]["step_id"] == "4.2"), {})
        good = {"integrity": {"PASS"}, "explicit_target_coverage": {"PASS"}, "shacl": {"CONFORMS"},
                "owl_profile": {"PASSED"}, "hermit": {"CONSISTENT"}}
        checks = {"integrity": integrity, **graph.get("checks", {})}
        def check_status(name):
            observed = checks.get(name, {}).get("status", "NOT_RUN")
            if observed in good[name]:
                return "PASS"
            if observed in {"NOT_RUN", "ERROR", "TIMEOUT", "UNSUPPORTED", "NOT_APPLICABLE"}:
                return observed
            return "FAIL"
        session["checks"] = [{"name": name, "required": True,
            "status": check_status(name),
            "candidate_digest": semantic_hash(sorted(source, key=lambda c: c["candidate_id"])), "dependency_digest": semantic_hash(session["frozen"]),
            "review_id": request.parameters["review_id"], "job_id": request.idempotency_key} for name in REQUIRED]
    save(root, session)


def canonical_operation(name):
    return {"modeling.candidate": "modeling.proposal", "modeling.cq": "modeling.prepare",
            "modeling.baseline": "modeling.prepare", "modeling.alignment": "modeling.prepare"}.get(name, name)


def require_checks(root, candidates, review_id):
    session = read(root)
    if not session:
        return
    digest = semantic_hash(sorted(candidates, key=lambda c: c["candidate_id"]))
    checks = session["checks"]
    # Compare canonical selection order, not incidental provider order.
    if len(checks) != len(REQUIRED) or {c["name"] for c in checks} != set(REQUIRED) or any(
        c["status"] != "PASS" or not c["required"] or c["candidate_digest"] != digest
        or c["dependency_digest"] != semantic_hash(session["frozen"]) or c["review_id"] != review_id for c in checks
    ):
        raise ServiceBoundaryError("REQUIRED_CHECKS_NOT_PASSED", "Run all required checks on the exact accepted selection and current dependencies", status_code=409)
