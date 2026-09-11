"""Local, version-bound action service and reviewed execution-policy evolution.

Only registered Python actions run. Domain assets supply declarative vocabulary
and exact state labels, never Python, SQL, prompts or executable permissions.
"""
from __future__ import annotations

from pathlib import Path
from time import perf_counter

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn
from zhigou_toolchain.contracts.document_io import atomic_write_json, read_document
from zhigou_toolchain.domain_packs.registry import DomainPackRegistry

from .errors import ServiceBoundaryError

OPERATIONS = frozenset({"task.plan", "task.execute", "business.inspect", "evolution.propose",
                       "evolution.evaluate", "evolution.review", "evolution.activate", "evolution.rollback", "module.evaluate"})
ACTIONS = {"create_work_order": {"version": "1.0.0", "permission": "action:work-order:create"}}


def load(root):
    path = Path(root) / "registry" / "business-state.json"
    return read_document(path, max_bytes=32 * 1024 * 1024) if path.exists() else {
        "schema_version": "1.0.0", "plans": {}, "orders": {}, "executions": {}, "candidates": {},
        "active": {"priority": "normal", "version": "1.0.0"}, "history": []}


def choose(state: str, policy: dict) -> str:
    """Unknown/negated statements cannot be coerced to positive findings."""
    return policy["states"].get(state, "VERIFY")


def decisions(objects, policy, configuration):
    return [{**item, "decision": choose(item["state"], policy), "priority": configuration["priority"]} for item in objects]


def _policy(app, project):
    registry = DomainPackRegistry(app.configuration.domain_packs_root)
    pack = registry.resolve(project.domain_pack, project.domain_pack_version)
    asset_id = pack.manifest.document.get("extensions", {}).get("x-execution-policy-asset")
    asset = next((a for a in pack.manifest.document["assets"] if a["asset_id"] == asset_id), None)
    if not asset:
        raise ServiceBoundaryError("ACTION_POLICY_UNSUPPORTED", "This Domain Pack has no registered local execution policy", status_code=422)
    # resolve() verifies pack lock and all asset digests before this read.
    policy = read_document(pack.root / asset["path"])
    if (policy.get("action") not in ACTIONS or not policy.get("states") or
            set(policy["states"].values()) - {"CREATE", "SKIP", "VERIFY"}):
        raise ServiceBoundaryError("ACTION_POLICY_INVALID", "Only registered actions and closed tri-state rules are allowed", status_code=422)
    return policy


def _read_objects(app, project, principal, package_id, policy):
    from .object_snapshot import read
    snapshot = read(app, project, principal, package_id, policy["class_iri"])
    terms = set(snapshot["vocabulary"])
    if not {policy[k] for k in ("class_iri", "state_predicate", "object_predicate")} <= terms:
        raise ServiceBoundaryError("ACTION_ONTOLOGY_MISMATCH", "Action vocabulary is absent from the fixed ontology version", status_code=409)
    objects = []
    for row in snapshot["objects"]:
        if any(p["object"]["term_type"] != ("LITERAL" if p["predicate"] == policy["state_predicate"] else "IRI")
               for p in row["properties"] if p["predicate"] in {policy["state_predicate"], policy["object_predicate"]}):
            raise ServiceBoundaryError("ACTION_PARAMETER_TYPE_INVALID", "State must be a literal and the business object must be an IRI", status_code=422)
        def values(predicate, row=row):
            return [p["object"]["value"] for p in row["properties"] if p["predicate"] == predicate]
        states, targets = values(policy["state_predicate"]), values(policy["object_predicate"])
        if len(states) != 1 or len(targets) != 1:
            raise ServiceBoundaryError("OBJECT_STATE_CONFLICT", "Action requires one unambiguous state and object reference", status_code=422)
        if not row["evidence"]:
            raise ServiceBoundaryError("ACTION_EVIDENCE_MISSING", "Action input has no verified source evidence", status_code=422)
        objects.append({"inspection": row["iri"], "object": targets[0], "state": states[0],
                        "evidence": row["evidence"], "object_version": row["object_version"]})
    return objects, {"semantic_digest": snapshot["semantic_digest"]}


def _find(state, group, identifier):
    value = state[group].get(identifier)
    if value is None:
        raise ServiceBoundaryError("BUSINESS_RECORD_NOT_FOUND", "Record is absent from this project", status_code=404)
    return value


def execute(app, project, request, principal):
    if request.operation_id == "module.evaluate":
        from .evaluation import execute as evaluate
        return evaluate(app, project, request, principal)
    started = perf_counter()
    state = load(project.root)
    name, params = request.operation_id, request.parameters
    result = {}
    if name == "business.inspect":
        return {**state, "actions": ACTIONS, "environment": "LOCAL", "external_deployment": "NOT_RUN"}
    if name == "task.plan":
        policy = _policy(app, project)
        objects, metadata = _read_objects(app, project, principal, params["package_id"], policy)
        content = {"project_id": project.project_id, "package_id": params["package_id"], "goal": params["goal"],
                   "planner_kind": "DETERMINISTIC_DOMAIN_POLICY", "goal_semantics": "AUDIT_DESCRIPTION_NOT_INTERPRETED",
                   "objects": objects, "policy": policy, "configuration": state["active"],
                   "semantic_digest": metadata["semantic_digest"], "action": ACTIONS[policy["action"]],
                   "items": decisions(objects, policy, state["active"]), "mode": "DETERMINISTIC"}
        identifier = stable_urn("task-plan", content)
        state["plans"][identifier] = {**content, "plan_id": identifier}
        result = {"plan": state["plans"][identifier]}
    elif name == "task.execute":
        plan = _find(state, "plans", params["plan_id"])
        permission = ACTIONS[plan["policy"]["action"]]["permission"]
        if not principal.can(permission):
            raise ServiceBoundaryError("ACTION_FORBIDDEN", "Current identity cannot invoke the registered action", status_code=403)
        if plan["configuration"] != state["active"]:
            raise ServiceBoundaryError("TASK_PLAN_STALE", "Replan after a reviewed execution configuration update", status_code=409)
        objects, metadata = _read_objects(app, project, principal, plan["package_id"], plan["policy"])
        if objects != plan["objects"] or metadata["semantic_digest"] != plan["semantic_digest"]:
            raise ServiceBoundaryError("TASK_OBJECTS_STALE", "Fixed object snapshot changed", status_code=409)
        receipts, pending = [], []
        for item in decisions(objects, plan["policy"], state["active"]):
            if item["decision"] == "VERIFY":
                pending.append(item)
            if item["decision"] != "CREATE":
                continue
            # Stable natural business identity is independent of request and
            # ontology package version: re-importing cannot create duplicates.
            key = semantic_hash({"project": project.project_id, "object": item["object"], "inspection": item["inspection"]})
            existed = key in state["orders"]
            if not existed:
                state["orders"][key] = {"order_id": key, "object": item["object"], "inspection": item["inspection"],
                    "status": "OPEN", "priority": item["priority"], "package_id": plan["package_id"], "plan_id": plan["plan_id"],
                    "evidence": item["evidence"], "object_version": item["object_version"],
                    "action_version": plan["action"]["version"], "configuration": plan["configuration"], "created_by": principal.principal_id}
            receipts.append({"order_id": key, "outcome": "EXISTING" if existed else "CREATED", "state_digest": semantic_hash(state["orders"][key])})
        identifier = stable_urn("task-execution", {"job": request.idempotency_key, "plan": plan["plan_id"]})
        execution = {"execution_id": identifier, "plan_id": plan["plan_id"], "package_id": plan["package_id"],
            "job_id": request.idempotency_key, "configuration": plan["configuration"], "receipts": receipts,
            "pending_verification": pending, "skipped": [i for i in plan["items"] if i["decision"] == "SKIP"],
            "mode": "DETERMINISTIC", "environment": "LOCAL", "status": "COMPLETED_WITH_PENDING" if pending else "COMPLETED"}
        state["executions"][identifier] = execution
        result = {"execution": execution}
    elif name == "evolution.propose":
        execution = _find(state, "executions", params["execution_id"])
        from packaging.version import Version
        if Version(params["version"]) <= Version(state["active"]["version"]):
            raise ServiceBoundaryError("EVOLUTION_VERSION_INVALID", "New candidates need a higher configuration version; use rollback for older versions", status_code=422)
        candidate = {"execution_id": execution["execution_id"], "base": state["active"],
            "configuration": {"priority": params["priority"], "version": params["version"]}, "feedback": params["feedback"],
            "created_by": principal.principal_id, "status": "CANDIDATE", "route": "EXECUTION_CONFIGURATION"}
        identifier = stable_urn("evolution-candidate", candidate)
        candidate["candidate_id"] = identifier
        # Repeating a proposal must not erase existing evaluation or approval.
        state["candidates"].setdefault(identifier, candidate)
        result = {"candidate": state["candidates"][identifier]}
    elif name in {"evolution.evaluate", "evolution.review", "evolution.activate"}:
        candidate = _find(state, "candidates", params["candidate_id"])
        if candidate["base"] != state["active"]:
            raise ServiceBoundaryError("EVOLUTION_BASE_STALE", "Candidate base no longer matches the active configuration", status_code=409)
        if name == "evolution.evaluate":
            execution = _find(state, "executions", candidate["execution_id"])
            plan = _find(state, "plans", execution["plan_id"])
            before = decisions(plan["objects"], plan["policy"], candidate["base"])
            after = decisions(plan["objects"], plan["policy"], candidate["configuration"])
            checks = [{"name": "preserve_object_decisions", "required": True,
                "status": "PASS" if [i["decision"] for i in before] == [i["decision"] for i in after] else "FAIL"},
                {"name": "configuration_changed", "required": True,
                 "status": "PASS" if candidate["configuration"] != candidate["base"] and before != after else "FAIL"}]
            candidate["evaluation"] = {"checks": checks, "before": before, "after": after,
                "data_digest": semantic_hash(plan["objects"]), "sample_size": len(before),
                "scope": "Deterministic engineering regression, not research completion-rate evidence"}
            candidate["status"] = "VALIDATED" if all(c["status"] == "PASS" for c in checks) else "REGRESSION_FAILED"
            candidate.pop("review", None)
        elif name == "evolution.review":
            if principal.principal_type != "HUMAN":
                raise ServiceBoundaryError("HUMAN_REVIEW_REQUIRED", "Evolution approval requires an authenticated human reviewer", status_code=403)
            if app.configuration.review_profile != "DEVELOPMENT_SINGLE_REVIEWER" and principal.principal_id == candidate["created_by"]:
                raise ServiceBoundaryError("INDEPENDENT_REVIEW_REQUIRED", "Production-profile candidates require an independent reviewer", status_code=403)
            if candidate["status"] != "VALIDATED":
                raise ServiceBoundaryError("EVOLUTION_REGRESSION_REQUIRED", "All required regression checks must pass before review", status_code=409)
            candidate["review"] = {"reviewer_id": principal.principal_id, "rationale": params["rationale"],
                "token_id": principal.token_id,
                "decision": params["decision"], "content_digest": semantic_hash({"configuration": candidate["configuration"], "evaluation": candidate["evaluation"]})}
            candidate["status"] = "APPROVED" if params["decision"] == "APPROVE" else "REJECTED"
        else:
            if candidate["status"] != "APPROVED" or candidate["review"]["content_digest"] != semantic_hash({"configuration": candidate["configuration"], "evaluation": candidate["evaluation"]}):
                raise ServiceBoundaryError("EVOLUTION_APPROVAL_REQUIRED", "Reviewed content and successful regression required", status_code=409)
            reviewer = app.tokens.resolve(candidate["review"]["token_id"])
            if reviewer.principal_type != "HUMAN" or not reviewer.can("evolution:review"):
                raise ServiceBoundaryError("EVOLUTION_REVIEW_REVOKED", "Reviewer authorization was revoked", status_code=403)
            state["history"].append({"candidate_id": candidate["candidate_id"], "before": state["active"], "after": candidate["configuration"], "activated_by": principal.principal_id})
            state["active"] = candidate["configuration"]
            candidate["status"] = "ACTIVE"
        result = {"candidate": candidate, "active": state["active"]}
    elif name == "evolution.rollback":
        if params["expected_configuration_digest"] != semantic_hash(state["active"]) or not state["history"]:
            raise ServiceBoundaryError("EVOLUTION_HEAD_CONFLICT", "Reload the active configuration and its history", status_code=409)
        previous = state["history"][-1]["before"]
        state["history"].append({"before": state["active"], "after": previous, "rollback_by": principal.principal_id, "rationale": params["rationale"]})
        state["active"] = previous
        result = {"active": state["active"], "status": "ROLLED_BACK"}
    else:
        raise ServiceBoundaryError("ACTION_UNREGISTERED", "Unknown business operation", status_code=422)
    atomic_write_json(Path(project.root) / "registry" / "business-state.json", state)
    persisted = load(project.root)
    if name == "task.execute":
        result["business_state"] = {"orders": list(persisted["orders"].values()), "readback_verified": True}
    return {**result, "duration_seconds": perf_counter() - started}
