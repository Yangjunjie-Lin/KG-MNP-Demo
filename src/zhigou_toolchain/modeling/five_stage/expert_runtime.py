"""One bounded review coordinator over real method calls in the original job.

No filesystem/model tools are granted to reviewers. The service supplies frozen
configuration, safe evidence and a closed patch adapter. Receipts are observations.
"""
from __future__ import annotations

import json
import re
from contextvars import ContextVar
from copy import deepcopy
from time import monotonic
from uuid import uuid4

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.delivery.trace import PRIVATE_KEYS, public_value

from .expert import (
    REVISION_PROMPT,
    ReviewResult,
    RevisionPatch,
    resolve_configuration,
    technical_decision,
)
from .tools import ToolBlocked

ACTIVE_EXPERT: ContextVar[ExpertRuntime | None] = ContextVar("expert_loop", default=None)


def safe_view(value):
    """Never send acceptance plans/answers, even to a reviewer. Not lossless."""
    excluded = PRIVATE_KEYS | {"cq_test_plan", "assertions", "test_results", "expected_answer_shape",
        "competency_question_ids", "independent_answers", "negative_cases", "test_plan", "test_cases"}
    if isinstance(value, dict):
        if value.get("manifest_kind") in {"KG_MNP_COMPETENCY_QUESTION_TEST_REPORT", "KG_MNP_CQ_TEST_PLAN"}:
            return {"report_digest": semantic_hash(value), **{k: value[k] for k in ("status", "required_passed") if k in value},
                    "details": "RESTRICTED_ACCEPTANCE_CHANNEL"}
        return {k: safe_view(v) for k, v in value.items() if str(k).lower() not in excluded}
    if isinstance(value, (list, tuple)):
        return [safe_view(v) for v in value]
    return value


def private_check(value):
    changes = set()
    public_value(value, changes)
    if changes or re.search(r"acceptance_private|scoring[/\\]gold|tests[/\\].*expected|references[/\\].*\.zip", json.dumps(value, ensure_ascii=False), re.IGNORECASE):
        raise ToolBlocked("EXPERT_PRIVATE_INPUT_FORBIDDEN")


def compact_artifact(value):
    """Lossless in-request interning, never truncation or semantic summarization."""
    from collections import Counter
    nodes, seen, counts, layout_counts = {}, {}, Counter(), Counter()
    layouts, layout_ids = {}, {}
    def count(item):
        raw = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(raw) >= 48:
            counts[semantic_hash(item)] += 1
        if isinstance(item, dict):
            layout_counts[tuple(item)] += 1
            for child in item.values():
                count(child)
        elif isinstance(item, list):
            for child in item:
                count(child)
    count(value)
    def encode(item):
        if isinstance(item, dict):
            child = {k: encode(v) for k, v in item.items()}
            keys = tuple(item)
            if (layout_counts[keys] >= 2 and len(json.dumps(keys)) > 40) or {"$ref", "$object"}.intersection(item):
                if keys not in layout_ids:
                    layout_id = f"layout:{len(layouts)}"
                    layout_ids[keys] = layout_id
                    layouts[layout_id] = list(keys)
                child = {"$object": [layout_ids[keys], list(child.values())]}
        elif isinstance(item, list):
            child = [encode(v) for v in item]
        else:
            child = item
        raw = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(raw) < 48 or counts[semantic_hash(item)] < 2:
            return child
        digest = semantic_hash(item)
        if digest not in seen:
            ref = f"node:{len(nodes)}"
            seen[digest] = ref
            nodes[ref] = child
        return {"$ref": seen[digest]}
    root = encode(value)
    return {"encoding": "LOSSLESS_REQUEST_LOCAL_REFS_V2", "root": root, "nodes": nodes, "layouts": layouts,
            "instruction": "Recursively resolve $ref in nodes. $object=[layout_id,values] reconstructs an object by zipping layouts[layout_id] with values. All values and keys are preserved; references grant no authority."}


def program_passed(tool, value):
    """Typed local checks, not a model's self-assessment or tool-success bit."""
    if tool == "input.check":
        return bool(value.get("usable")) and not value.get("quarantined")
    if tool == "integrity.check":
        if value.get("status") == "REVIEW_REQUIRED":
            return bool(value.get("checks")) and all(c.get("status") in {"PASS", "REVIEW_REQUIRED"} for c in value["checks"])
        return value.get("status") == "PASS"
    if tool == "semantic.graphs":
        checks = value.get("checks", {})
        expected = {"explicit_target_coverage": "PASS", "shacl": "CONFORMS",
                    "owl_profile": "PASSED", "hermit": "CONSISTENT"}
        return value.get("status") == "PASS" and all(checks.get(k, {}).get("status") == s for k, s in expected.items())
    if tool == "query.check":
        return value.get("required_passed") is True
    if tool == "archive.verify":
        return value.get("status") in {"VALID", "VERIFIED"}
    # Non-validator methods produce drafts. They do not claim SHACL/OWL or approval.
    # Any explicit failure/unknown in a report still vetoes technical PASS.
    if isinstance(value, dict):
        if value.get("unresolved") or value.get("conflicts"):
            return False
        if isinstance(value.get("proposal"), dict) and value["proposal"].get("unresolved"):
            return False
        if tool == "scope.suggest" and any(a.get("content", {}).get("proposal", {}).get("unresolved")
                for a in value.get("five_stage", {}).get("artifacts", []) if a.get("ref", {}).get("step_id") == "1.3"):
            return False
        if value.get("status") in {"FAIL", "FAILED", "ERROR", "UNKNOWN", "NOT_RUN", "TIMEOUT", "BLOCKED"}:
            return False
    return value is not None


def business_fingerprint(result):
    """Candidate identity excludes varying validator timings and review receipts."""
    proposal = result.get("proposal") or result.get("expert_routed_proposal") or {}
    groups = ("tbox_candidates", "abox_candidates", "mapping_candidates", "shacl_candidates")
    candidates = [c for group in groups for c in proposal.get(group, [])] if any(k in proposal for k in groups) else None
    if candidates is None:
        candidates = next((a["content"] for a in result.get("five_stage", {}).get("artifacts", [])
                           if a["ref"]["step_id"] == "3.6"), None)
    if candidates is not None:
        values = [{k: c.get(k) for k in ("candidate_kind", "candidate_action", "body", "evidence_refs", "kg_ir_item_refs")} for c in candidates]
        return semantic_hash({"candidate_business": sorted(values, key=semantic_hash)})
    for key in ("proposal", "expert_routed_proposal", "scope", "plan"):
        if isinstance(result.get(key), dict):
            return semantic_hash({key: result[key]})
    manifest = result.get("manifest")
    if isinstance(manifest, dict) and manifest.get("package_id"):
        return semantic_hash({"native_package_id": manifest["package_id"]})
    for artifact in result.get("five_stage", {}).get("artifacts", []):
        if artifact["ref"]["step_id"] == "1.3":
            return semantic_hash({"scope_draft": artifact["content"]["proposal"]})
    return semantic_hash(safe_view(result))


def usage_summary(calls):
    unique = {c["physical_call_id"]: c for c in calls}
    totals = {"input_tokens": 0, "output_tokens": 0}
    unknown = {k: [] for k in totals}
    groups, scenarios = {}, {}
    for cid, call in unique.items():
        key = f"S{call.get('stage_id')}/{call.get('method_id')}/{call.get('purpose')}"
        groups.setdefault(key, []).append(cid)
        if call.get("scenario_id"):
            scenario_key = call["scenario_id"] + "/" + call["effective_configuration_digest"]
            scenarios.setdefault(scenario_key, []).append(cid)
        for field in totals:
            value = call.get("usage", {}).get(field)
            if type(value) is int and value >= 0:
                totals[field] += value
            else:
                unknown[field].append(cid)
    return {"physical_calls": len(unique), "known_subtotal": totals,
            "totals": {k: None if unknown[k] else v for k, v in totals.items()},
            "unknown_call_ids": unknown, "groups": groups, **({"scenario_configuration_groups": scenarios} if scenarios else {})}


class ExpertRuntime:
    def __init__(self, versions, *, guard, sources, client_factory, feedback=(), scenario=None):
        self.versions = deepcopy(versions)
        from .scenarios import require_current
        require_current(scenario)
        self.scenario = deepcopy(scenario)
        self.guard = guard
        self.sources = deepcopy(sources)
        private_check(self.sources)
        self.client_factory = client_factory
        self.feedback = deepcopy(list(feedback))
        private_check(self.feedback)
        self.loop_id = "expert-loop:" + uuid4().hex
        self.round = 0
        self.network_retry = 0
        self.purpose = "GENERATE"
        self.methods = []
        self.calls = []
        self.rounds = []
        self.started = monotonic()
        self.active_config = None
        budgets = [v["configuration"]["budget"] for v in versions.values()]
        self.budget = {k: min(b[k] for b in budgets) for k in budgets[0]}

    def check(self):
        self.guard()
        if monotonic() - self.started >= self.budget["max_seconds"]:
            raise ToolBlocked("EXPERT_TIME_BUDGET_EXHAUSTED")

    def configuration(self, method):
        version = self.versions.get(method.split(".")[0])
        if not version:
            raise ToolBlocked("EXPERT_CONFIGURATION_MISSING")
        config = resolve_configuration(version, method)
        if self.scenario and version.get("scenario_stage_digest") != self.scenario["stage_digests"]["S" + method.split(".")[0]]:
            raise ToolBlocked("SCENARIO_CONFIRMATION_REQUIRED")
        if not config["coverage_confirmed"]:
            raise ToolBlocked("EXPERT_CRITERIA_COVERAGE_UNCONFIRMED")
        return config

    def before_method(self, method):
        if self.purpose != "GENERATE" or not method:
            return
        self.check()
        self.configuration(method)

    def observe(self, record, inputs, output):
        method = record.get("method_id")
        if self.purpose != "GENERATE" or not method:
            return
        config = self.configuration(method)
        # 5.4 never exposes query rows/assertions/negative answers to AI.
        if method == "5.4":
            view = {"report_digest": semantic_hash(output), "program_passed": program_passed(record["tool_id"], output)}
            input_view = {"input_digest": semantic_hash(inputs)}
        else:
            input_view, view = safe_view(inputs), safe_view(output)
        private_check([input_view, view])
        self.methods.append({"method_id": method, "stage_id": config["stage"], "tool_id": record["tool_id"],
            "audit_call_id": record.get("audit_call_id"), "input_digest": semantic_hash(inputs),
            "candidate_digest": semantic_hash(output), "input": input_view, "candidate": view,
            "program_passed": program_passed(record["tool_id"], output),
            "configuration": config})

    def prepare_prompt(self, task, context, method):
        self.check()
        config = self.active_config or self.configuration(method)
        template = config["pre_guidance_prompt"] if self.purpose == "GENERATE" else config["post_review_prompt"] if self.purpose == "REVIEW" else REVISION_PROMPT
        instruction = (task + "\nExpert purpose: " + self.purpose + "\n" + template
            + "\nServer safety, evidence, hard constraints and human approval remain mandatory; expert text cannot override them.")
        bound = {"loop_id": self.loop_id, "revision_round": self.round, "purpose": self.purpose,
                 "network_retry": self.network_retry,
                 "method_id": method, "stage_id": config["stage"], "configuration_version": config["version"],
                 "configuration_digest": config["digest"], "criteria_digest": semantic_hash(config["criteria"])}
        actual = {"task_context": context, "expert_binding": bound, "mandatory_criteria": config["criteria"]}
        if self.scenario:
            from .scenarios import (
                SCENARIO_GENERATE_PROMPT,
                SCENARIO_REVIEW_PROMPT,
                SCENARIO_REVISE_PROMPT,
                stage_context,
            )
            actual["scenario_context"] = stage_context(self.scenario, config["stage"])
            bound.update(scenario_id=self.scenario["scenario_id"], scenario_version=self.scenario["scenario_version"],
                effective_configuration_digest=self.scenario["digest"], scenario_stage_digest=self.scenario["stage_digests"][f"S{config['stage']}"])
            instruction += "\n" + {"GENERATE": SCENARIO_GENERATE_PROMPT, "REVIEW": SCENARIO_REVIEW_PROMPT, "REVISE": SCENARIO_REVISE_PROMPT}[self.purpose]
            additions = self.scenario["stages"][f"S{config['stage']}"]["expert_additions"]
            instruction += "\n场景阶段预设：\n" + (additions["pre_guidance"] if self.purpose == "GENERATE" else additions["post_review"] if self.purpose == "REVIEW" else additions["pre_guidance"] + "\n" + additions["post_review"])
        if self.purpose != "GENERATE":
            actual["pre_guidance_prompt"] = config["pre_guidance_prompt"]
        private_check([instruction, actual])
        return instruction, actual, bound

    def before_request(self, payload):
        self.check()
        if len(self.calls) >= self.budget["max_model_calls"]:
            raise ToolBlocked("EXPERT_CALL_BUDGET_EXHAUSTED")
        usage = usage_summary(self.calls)
        if any(usage["unknown_call_ids"].values()):
            # Unknown billing is never zero. Stop instead of exceeding a token cap.
            raise ToolBlocked("EXPERT_TOKEN_USAGE_UNKNOWN")
        consumed = sum(usage["known_subtotal"].values())
        # UTF-8 byte count is only a conservative reservation, not reported usage.
        reserve = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + self.budget["max_output_tokens"]
        if consumed + reserve > self.budget["max_tokens"]:
            raise ToolBlocked("EXPERT_TOKEN_BUDGET_EXHAUSTED")

    def physical_result(self, scope, error):
        if not scope.get("dispatched"):
            return
        binding = scope.get("expert_binding", {})
        self.calls.append({"physical_call_id": scope.get("audit_call_id") or scope.get("call_id") or scope["physical_call_id"],
            "audit_call_id": scope.get("audit_call_id"), "transport_call_id": scope.get("call_id"),
            "usage": deepcopy(scope["usage"]), "status": "FAILED" if error else "SUCCEEDED",
            **binding})

    def ask(self, method, purpose, context, schema, *, evidence):
        from .agents import invoke
        self.purpose, self.active_config = purpose, self.configuration(method)
        client = self.client_factory()
        client.max_output_tokens = self.budget["max_output_tokens"]
        try:
            for retry in range(self.budget["max_network_retries"] + 1):
                self.network_retry = retry
                self.check()
                try:
                    return invoke(int(method[0]), "expert.review" if purpose == "REVIEW" else "expert.revise",
                        lambda: client.propose("Review the supplied real method artifact." if purpose == "REVIEW" else "Propose only the closed allowed patch.",
                            context, schema, evidence_ids=evidence), inputs=context, method_id=method)
                except ToolBlocked as exc:
                    transport = getattr(client, "last_transport_error", {})
                    # Timeouts may have executed remotely. Never replay unknown requests.
                    if (str(exc) != "MODEL_ENDPOINT_OR_RESPONSE_INVALID" or retry == self.budget["max_network_retries"]
                            or transport.get("http_status") not in {429, 502, 503}):
                        raise
        finally:
            client.close()
            self.active_config = None
            self.purpose = "GENERATE"
            self.network_retry = 0

    def run(self, produce, revise):
        """The only business revision loop. Adapters re-run original programs."""
        result, seen, pending_patch = None, set(), None
        stop, decision = None, "ESCALATE"
        try:
            for revision in range(self.budget["max_revision_rounds"] + 1):
                self.round, self.methods = revision, []
                self.check()
                result = produce(pending_patch)
                overall_program_passed = program_passed("operation.result", result) and program_passed("automatic.validation", result.get("automatic_validation", {}))
                digest = semantic_hash(safe_view(result))
                business_digest = business_fingerprint(result)
                if business_digest in seen:
                    stop = "EXPERT_OSCILLATION_OR_NO_CHANGE"
                    break
                seen.add(business_digest)
                reviews = []
                row = {"revision_round": revision, "candidate_digest": digest, "business_digest": business_digest, "methods": reviews,
                       "patch_digest": semantic_hash(pending_patch) if pending_patch else None, "overall_program_passed": overall_program_passed}
                self.rounds.append(row)
                if not self.methods:
                    stop = "EXPERT_METHOD_RECEIPT_MISSING"
                    break
                try:
                    patch_targets = revise(result, None, [], digest)
                except ToolBlocked:
                    patch_targets = {"status": "NO_AUTOMATIC_PATCH_ADAPTER"}
                for observed in self.methods:
                    self.check()
                    evidence = {"input:" + observed["input_digest"], "output:" + observed["candidate_digest"], *self.sources}
                    scene_views = [v for v in result.get("scenario_outputs", []) if v["stage_id"] == observed["stage_id"]]
                    evidence.update("scenario-output:" + semantic_hash(v) for v in scene_views)
                    call = self.ask(observed["method_id"], "REVIEW", {
                        "artifact": {k: v for k, v in observed.items() if k not in {"configuration", "input", "candidate"}},
                        "material": compact_artifact({"input": observed["input"], "candidate": observed["candidate"],
                            "allowed_patch_targets": safe_view(patch_targets)}),
                        "evidence": sorted(evidence), "sources": self.sources, "human_feedback": self.feedback,
                        **({"scenario_output_views": scene_views} if scene_views else {}),
                        "issue_location_contract": "For an editable target, locate issues as target.field or target.body.field using these exact target keys; otherwise return a diagnostic location and ESCALATE.",
                        "program_report": {"passed": observed["program_passed"] and overall_program_passed,
                            "method_passed": observed["program_passed"], "overall_program_passed": overall_program_passed,
                            "overall_result_digest": digest, "ref": observed.get("audit_call_id")}},
                        ReviewResult.model_json_schema(), evidence=evidence)
                    review = ReviewResult.model_validate(call["proposal"]).model_dump()
                    private_check(review)
                    verdict = technical_decision(review, observed["configuration"], evidence, program_passed=observed["program_passed"] and overall_program_passed)
                    reviews.append({"review_id": "ai-review:" + uuid4().hex, "actor": "AI", "method_id": observed["method_id"],
                        "candidate_digest": observed["candidate_digest"], "input_digest": observed["input_digest"],
                        "configuration_digest": observed["configuration"]["digest"], "configuration_version": observed["configuration"]["version"],
                        "criteria_digest": semantic_hash(observed["configuration"]["criteria"]),
                        "program_passed": observed["program_passed"] and overall_program_passed, "method_program_passed": observed["program_passed"],
                        "program_report_ref": observed.get("audit_call_id"),
                        "decision": verdict, "review": review, "model_call": deepcopy(self.calls[-1]) if self.calls else None})
                if all(r["decision"] == "PASS" for r in reviews):
                    self.check()
                    decision, stop = "PASS", "LATEST_VERSION_TECHNICALLY_PASSED"
                    break
                if any(r["decision"] == "ESCALATE" for r in reviews):
                    stop = "EXPERT_DECISION_REQUIRED"
                    break
                if revision == self.budget["max_revision_rounds"]:
                    stop = "EXPERT_REVISION_BUDGET_EXHAUSTED"
                    break
                failed = [r for r in reviews if r["decision"] == "REVISE"]
                issues = [dict(i, method_id=r["method_id"]) for r in failed for i in r["review"]["issues"]]
                if not issues or len({i["issue_id"] for i in issues}) != len(issues):
                    stop = "EXPERT_PATCH_ISSUES_REQUIRED"
                    break
                patch_context = revise(result, None, issues, digest)
                target_stage = min(i["target_stage"] for i in issues)
                revision_method = failed[0]["method_id"] if int(failed[0]["method_id"][0]) == target_stage else {1: "1.3", 2: "2.5", 3: "3.6", 4: "4.3", 5: "5.1"}[target_stage]
                call = self.ask(revision_method, "REVISE", {
                    "base_digest": digest, "issues": issues, "allowed_targets": patch_context,
                    "sources": self.sources, "human_feedback": self.feedback}, RevisionPatch.model_json_schema(), evidence=set(self.sources))
                patch = RevisionPatch.model_validate(call["proposal"]).model_dump()
                private_check(patch)
                if patch["base_digest"] != digest or patch["unresolved"]:
                    stop = "EXPERT_PATCH_BASE_OR_UNRESOLVED"
                    break
                pending_patch = revise(result, patch, issues, digest)
                row["patch"] = patch
                row["changes"] = pending_patch["changes"]
        except ToolBlocked as exc:
            stop = str(exc) if str(exc).replace("_", "").isalnum() else "EXPERT_MODEL_OR_PATCH_ERROR"
        return result, {"loop_id": self.loop_id, "status": "PASSED" if decision == "PASS" else "ESCALATED",
            "decision": decision, "stop_reason": stop, "rounds": self.rounds, "revision_round": self.round,
            "calls": self.calls, "token_usage": usage_summary(self.calls), "human_approval": "NOT_GRANTED",
            "network_retry_calls": sum(c.get("network_retry", 0) > 0 for c in self.calls),
            "configuration_digests": {s: v["digest"] for s, v in self.versions.items()}}
