"""Synthetic experts and MockTransport only; never human acceptance or LIVE."""
import json
from copy import deepcopy

import httpx
import pytest

from zhigou_toolchain.modeling.five_stage.expert import (
    ExpertConfiguration,
    default_configuration,
    resolve_configuration,
    technical_decision,
)


@pytest.mark.parametrize("stage", range(1, 6))
def test_defaults_are_unconfirmed_and_inherited(stage):
    config = default_configuration(stage)
    assert config["status"] == "DRAFT"
    assert config["confirmed_by"] is None
    parsed = ExpertConfiguration.model_validate(config["configuration"])
    assert parsed.pre_guidance_prompt and parsed.post_review_prompt
    with pytest.raises(ValueError, match="EXPERT_CONFIGURATION_UNCONFIRMED"):
        resolve_configuration(config, f"{stage}.1")
    config.update(status="CONFIRMED", confirmed_by="synthetic-expert")
    resolved = resolve_configuration(config, f"{stage}.1")
    assert resolved["configuration_source"] == "STAGE_DEFAULT"
    assert resolved["pre_guidance_prompt"] == parsed.pre_guidance_prompt


@pytest.mark.parametrize("stage", range(1, 6))
@pytest.mark.parametrize("defect", ["program", "missing", "unknown", "forged", "blocking"])
def test_model_pass_never_overrides_hard_gate(stage, defect):
    config = default_configuration(stage)
    config.update(status="CONFIRMED", confirmed_by="synthetic-expert")
    resolved = resolve_configuration(config, f"{stage}.1")
    result = {"decision": "PASS", "summary": "synthetic", "issues": [], "checks": [
        {"criterion_id": c["criterion_id"], "status": "PASS", "reason": "checked",
         "evidence_refs": ["output:abc"]} for c in resolved["criteria"]]}
    if defect == "missing":
        result["checks"].pop()
    if defect == "unknown":
        result["checks"][0]["status"] = "UNKNOWN"
    if defect == "forged":
        result["checks"][0]["evidence_refs"] = ["output:invented"]
    if defect == "blocking":
        result["issues"] = [{"severity": "BLOCKING"}]
    assert technical_decision(result, resolved, {"output:abc"},
                              program_passed=defect != "program") != "PASS"


def test_method_override_cannot_remove_required_criteria():
    config = default_configuration(1)
    config.update(status="CONFIRMED", confirmed_by="synthetic-expert")
    config["configuration"]["method_overrides"] = {"1.3": {"pre_guidance_prompt": "Specific synthetic guidance"}}
    before = deepcopy(config)
    resolved = resolve_configuration(config, "1.3")
    assert resolved["pre_guidance_prompt"] == "Specific synthetic guidance"
    assert resolved["criteria"] == config["configuration"]["criteria"]
    assert resolved["configuration_source"] == "METHOD_OVERRIDE"
    assert config == before


@pytest.mark.parametrize("stage", range(1, 6))
@pytest.mark.parametrize("qwen", [False, True])
@pytest.mark.parametrize("mode", ["PASS", "REPAIR", "EXHAUST", "NO_CHANGE", "EVIDENCE", "UNAUTHORIZED", "MODEL_ERROR"])
def test_bounded_coordinator_matrix(tmp_path, stage, qwen, mode):
    """Coordinator contract tests; adapters/real compiler separately service-tested."""
    from tests.upgrade.test_evolution_delivery import recorder
    from zhigou_toolchain.modeling.five_stage.agents import ACTIVE, AgentRun, invoke
    from zhigou_toolchain.modeling.five_stage.audit import ACTIVE_AUDIT, StepAudit
    from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
    from zhigou_toolchain.modeling.five_stage.coverage import (
        reconcile_physical_requests,
    )
    from zhigou_toolchain.modeling.five_stage.expert_runtime import (
        ACTIVE_EXPERT,
        ExpertRuntime,
        usage_summary,
    )
    from zhigou_toolchain.modeling.five_stage.tools import (
        ModelLock,
        QwenClient,
        ToolBlocked,
    )
    versions = {str(s): default_configuration(s) for s in range(1, 6)}
    for version in versions.values():
        version.update(status="CONFIRMED", confirmed_by="synthetic-expert")
        version["configuration"]["coverage_confirmed"] = True
    observed = []
    calls = {"reviews": 0, "revisions": 0}
    def http(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "mock"}]})
        payload = json.loads(request.content)
        observed.append(payload)
        actual = json.loads(payload["messages"][1]["content"])
        binding, data = actual["expert_binding"], actual["task_context"]
        if mode == "MODEL_ERROR":
            return httpx.Response(400, json={"error": "synthetic", "usage": {"prompt_tokens": 10, "completion_tokens": 2}})
        if binding["purpose"] == "REVIEW":
            calls["reviews"] += 1
            decision = "PASS" if mode == "PASS" or (mode == "REPAIR" and binding["revision_round"] == 2) else "REVISE"
            evidence = next(r for r in data["evidence"] if r.startswith("output:"))
            checks = [{"criterion_id": c["criterion_id"], "status": "PASS", "reason": "Synthetic", "evidence_refs": [evidence]}
                      for c in actual["mandatory_criteria"]]
            response = {"decision": decision, "checks": checks, "summary": "Synthetic only", "issues": []}
            if decision != "PASS":
                response["issues"] = [{"issue_id": "i", "criterion_id": checks[0]["criterion_id"], "severity": "BLOCKING",
                    "location": "draft", "description": "synthetic change", "suggestion": "revise", "target_stage": stage,
                    "evidence_refs": ["rule:0"]}]
            if mode == "EVIDENCE":
                checks[0]["evidence_refs"] = []
        else:
            calls["revisions"] += 1
            response = {"base_digest": data["base_digest"], "unresolved": [], "changes": [{"target": "draft",
                "field": "label", "value": "supported", "issue_id": "i", "evidence_ref": "rule:0", "quote": "supported", "quote_start": 0}]}
        return httpx.Response(200, json={"model": "mock", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(response)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2}})
    def factory():
        return (QwenClient if qwen else CompatibleClient)(ModelLock("mock", "synthetic-r1", "https://mock.invalid/v1"), transport=httpx.MockTransport(http))
    runtime = ExpertRuntime(versions, guard=lambda: None, sources={"rule:0": {"text": "supported"}}, client_factory=factory)
    tool, method = {1: ("scope.validate", "1.3"), 2: ("structure.design", "2.5"), 3: ("facts.normalize", "3.6"),
                    4: ("repair.route", "4.3"), 5: ("compile.plan", "5.1")}[stage]
    counter = {"version": 0}
    def produce(patch):
        if patch:
            counter["version"] += 0 if mode == "NO_CHANGE" else 1
        return invoke(stage, tool, lambda: dict(counter), inputs={"rule": "supported"}, method_id=method)
    def revise(result, patch, issues, digest):
        if patch is None:
            return {"draft": result}
        if mode == "UNAUTHORIZED":
            raise ToolBlocked("EXPERT_PATCH_OPERATION_FORBIDDEN")
        return {"changes": [{"before": result, "after": "synthetic change"}]}
    trace, audit = recorder(), StepAudit(tmp_path, {"job_id": "synthetic"}, content=True)
    at, rt, et = ACTIVE_AUDIT.set(audit), ACTIVE.set(AgentRun("synthetic", "task", "1", [])), ACTIVE_EXPERT.set(runtime)
    try:
        with trace.activate():
            _, result = runtime.run(produce, revise)
    finally:
        ACTIVE_EXPERT.reset(et)
        ACTIVE.reset(rt)
        ACTIVE_AUDIT.reset(at)
    snapshot = trace.finish("success", {})
    events = [json.loads(p.read_bytes()) for p in sorted(tmp_path.glob("*.json"))]
    assert reconcile_physical_requests(observed, events, snapshot)["physical_requests"] == len(observed)
    assert result["token_usage"]["physical_calls"] == len(observed)
    assert usage_summary(runtime.calls + runtime.calls) == result["token_usage"]
    assert result["token_usage"]["known_subtotal"] == {"input_tokens": len(observed)*10, "output_tokens": len(observed)*2}
    if mode in {"PASS", "REPAIR"}:
        assert result["decision"] == "PASS"
        assert calls["reviews"] == (1 if mode == "PASS" else 3)
        assert calls["revisions"] == (0 if mode == "PASS" else 2)
    else:
        assert result["decision"] == "ESCALATE"
        assert result["stop_reason"]
    if mode == "EXHAUST":
        assert calls == {"reviews": 4, "revisions": 3}
    for payload in observed:
        actual = json.loads(payload["messages"][1]["content"])
        assert actual["expert_binding"]["revision_round"] <= 3
        assert actual["expert_binding"]["configuration_digest"] == versions[str(stage)]["digest"]
    # Real transport turn starts at 1, independent of business round zero.
    assert [e["turn"] for e in snapshot["events"] if e["event"] == "llm_call"] == list(range(1, len(observed)+1))


def test_lossless_compaction_roundtrip_and_private_veto():
    from zhigou_toolchain.modeling.five_stage.expert_runtime import (
        compact_artifact,
        private_check,
    )
    value = {"records": [{"original_immutable_source_reference": "long immutable source reference:" + "1" * 100,
                          "current_business_literal_value": i} for i in range(30)],
             "reserved_user_keys": {"$ref":"raw-user-data", "$object":["raw", [1, 2]]}}
    packed = compact_artifact(value)
    def expand(item):
        if isinstance(item, dict):
            if set(item) == {"$ref"}:
                return expand(packed["nodes"][item["$ref"]])
            if set(item) == {"$object"}:
                layout, values = item["$object"]
                return dict(zip(packed["layouts"][layout], (expand(v) for v in values), strict=True))
            return {k: expand(v) for k, v in item.items()}
        return [expand(v) for v in item] if isinstance(item, list) else item
    assert expand(packed["root"]) == value
    assert packed["layouts"]
    assert len(json.dumps(packed)) < len(json.dumps(value))
    with pytest.raises(ValueError, match="PRIVATE"):
        private_check({"feedback": '{"corrected_answer":"private canary"}'})


@pytest.mark.parametrize("qwen", [False, True])
@pytest.mark.parametrize("stage", range(1, 6))
def test_generation_uses_confirmed_guidance_at_original_post_boundary(tmp_path, qwen, stage):
    from zhigou_toolchain.modeling.five_stage.agents import ACTIVE, AgentRun, invoke
    from zhigou_toolchain.modeling.five_stage.audit import ACTIVE_AUDIT, StepAudit
    from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
    from zhigou_toolchain.modeling.five_stage.expert_runtime import (
        ACTIVE_EXPERT,
        ExpertRuntime,
    )
    from zhigou_toolchain.modeling.five_stage.tools import ModelLock, QwenClient
    version = default_configuration(stage)
    version.update(status="CONFIRMED", confirmed_by="synthetic", version=3)
    version["configuration"]["coverage_confirmed"] = True
    seen = []
    def http(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "mock"}]})
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"model": "mock", "choices": [{"finish_reason": "stop", "message": {"content": '{"value":"source-bound"}'}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2}})
    def factory():
        return (QwenClient if qwen else CompatibleClient)(ModelLock("mock", "r1", "https://mock.invalid/v1"), transport=httpx.MockTransport(http))
    runtime = ExpertRuntime({str(stage): version}, guard=lambda: None, sources={}, client_factory=factory)
    audit, client = StepAudit(tmp_path, {"job_id": "synthetic"}), factory()
    at, rt, et = ACTIVE_AUDIT.set(audit), ACTIVE.set(AgentRun("s", "t", "1", [])), ACTIVE_EXPERT.set(runtime)
    tool = {1:"scope.suggest", 2:"structure.design", 3:"text.extract", 4:"repair.route", 5:"compile.plan"}[stage]
    try:
        invoke(stage, tool, lambda: client.propose("Existing business instruction", {"source":"authorized"},
            {"type":"object","properties":{"value":{"type":"string"}},"required":["value"],"additionalProperties":False}), inputs={})
    finally:
        ACTIVE_EXPERT.reset(et)
        ACTIVE.reset(rt)
        ACTIVE_AUDIT.reset(at)
        client.close()
    assert len(seen) == 1
    assert version["configuration"]["pre_guidance_prompt"] in seen[0]["messages"][0]["content"]
    data = json.loads(seen[0]["messages"][1]["content"])
    assert data["expert_binding"]["configuration_version"] == 3
    assert data["expert_binding"]["purpose"] == "GENERATE"
    assert runtime.calls[0]["usage"] == {"input_tokens": 5, "output_tokens": 2}


def test_project_manifest_required_but_legacy_reader_compatible():
    from zhigou_toolchain.modeling.delivery.evolution import validate_batch
    with pytest.raises(ValueError, match="UPSTREAM_MANIFEST_REQUIRED"):
        validate_batch({}, producer=True)
    assert validate_batch({})["status"] == "LOCAL_PROTOCOL_VALID"


@pytest.mark.parametrize("stage", [1, 2, 3, 5])
@pytest.mark.parametrize("bad", [None, "source", "target", "quote", "issue", "same"])
def test_production_closed_patch_adapter(stage, bad):
    from zhigou_toolchain.services.modeling_expert import validate_patch
    operation = {1:"modeling.scope", 2:"modeling.proposal", 3:"modeling.proposal", 5:"compile.plan.exact"}[stage]
    target, field = {1:("scope", "description"), 2:("draft", "label"), 3:("draft", "literal"), 5:("plan", "package_name")}[stage]
    targets = {target: {field: "old"}} if stage in {1, 5} else {target: {"draft_kind": "TBOX" if stage == 2 else "ABOX",
        "candidate_action": "CREATE_NEW" if stage == 2 else "ASSERT", "kg_ir_item_refs": ["source"],
        "body": {"candidate_type": "CLASS" if stage == 2 else "DATA_PROPERTY_ASSERTION", "label": "old",
                 "literal": {"lexical_value": "old"}}}}
    issues = [{"issue_id": "i", "target_stage": stage, "location": target + (".body." if stage in {2, 3} else ".") + field, "evidence_refs": ["source"]}]
    change = {"target": target, "field": field, "value": "new", "issue_id": "i", "evidence_ref": "source", "quote": "new", "quote_start": 0}
    if bad == "source": change["evidence_ref"] = "unknown"
    if bad == "target": change["target"] = "final.ttl"
    if bad == "quote": change["quote"] = "forged"
    if bad == "issue": change["issue_id"] = "made-up"
    if bad == "same": change.update(value="old", quote="old", quote_start=4)
    patch = {"changes": [change]}
    original = deepcopy(targets)
    if bad:
        with pytest.raises(ValueError):
            validate_patch(targets, patch, issues, {"source":{"text":"new old"}}, operation)
    else:
        result = validate_patch(targets, patch, issues, {"source":{"text":"new old"}}, operation)
        assert result["changes"][0]["before"] != result["changes"][0]["after"]
    assert targets == original


def test_production_patch_cannot_weaken_shacl_or_redefine_baseline():
    from zhigou_toolchain.services.modeling_expert import validate_patch
    issues = [{"issue_id":"i","target_stage":2,"location":"d.body.label","evidence_refs":["source"]}]
    patch = {"changes":[{"target":"d","field":"label","value":"new","issue_id":"i","evidence_ref":"source","quote":"new","quote_start":0}]}
    for kind, action in [("SHACL", "CONSTRAIN"), ("TBOX", "REUSE_EXISTING")]:
        with pytest.raises(ValueError, match="STRUCTURE_OR_RULE_FORBIDDEN"):
            validate_patch({"d":{"draft_kind":kind,"candidate_action":action,"body":{"label":"old"}}}, patch,
                           issues, {"source":{"text":"new"}}, "modeling.proposal")


def test_composite_review_invalidation_tracks_methods_not_only_job():
    from zhigou_toolchain.services.modeling_expert import require_pass
    from zhigou_toolchain.services.modeling_sessions import invalidate
    versions = {str(s): default_configuration(s) for s in range(1, 6)}
    session = {"revision":1,"events":[],"checks":[],"outputs":[{"stage":3,"operation":"modeling.proposal","digest":"current", "status":"CURRENT"}],
        "expert":{"enabled":True,"stages":versions,"loops":[{"operation":"modeling.proposal","current":True,
            "decision":"PASS","output_digest":"current","methods":[{"method_id":f"{s}.1","stage_id":s,"current":True,
                "configuration_digest":versions[str(s)]["digest"]} for s in (2, 3, 4)]}]}}
    invalidate(session, 4, "New S4 check")
    require_pass(session, "modeling.proposal")
    assert session["expert"]["loops"][0]["methods"][-1]["current"] is False
    invalidate(session, 3, "New facts")
    with pytest.raises(Exception, match="current|stale"):
        require_pass(session, "modeling.proposal")


@pytest.mark.parametrize("operation", ["package.export", "package.verify", "compile.validate", "registry.import", "modeling.handoff.export"])
def test_direct_operation_cannot_borrow_another_package_pass(operation):
    from zhigou_toolchain.services.errors import ServiceBoundaryError
    from zhigou_toolchain.services.modeling_expert import before
    from zhigou_toolchain.services.models import OperationRequest
    session = {"outputs":[{"operation":"compile.build","stage":5,"identifier":"current-package","digest":"d","status":"CURRENT"}],
        "expert":{"enabled":True,"stages":{"5":{"digest":"cfg"}},"loops":[{"operation":"compile.build","current":True,
            "decision":"PASS","output_digest":"d","methods":[{"method_id":"5.1","stage_id":5,"configuration_digest":"cfg","current":True}]}]}}
    with pytest.raises(ServiceBoundaryError, match="package"):
        before(session, OperationRequest(operation, "synthetic", {"package_id":"different-unreviewed-package"}))


def test_export_snapshot_cannot_borrow_new_review_conditions():
    from zhigou_toolchain.services.errors import ServiceBoundaryError
    from zhigou_toolchain.services.modeling_expert import require_package
    session = {"outputs":[{"operation":"compile.build","stage":5,"identifier":"p","digest":"d","status":"CURRENT"}],
        "expert":{"enabled":True,"stages":{"5":{"digest":"new-cfg"}},"loops":[{"operation":"compile.build","current":True,
            "decision":"PASS","output_digest":"d","methods":[{"method_id":"5.1","stage_id":5,"configuration_digest":"new-cfg","current":True}]}]}}
    with pytest.raises(ServiceBoundaryError, match="conditions"):
        require_package(session, "p", export_result={"expert_loop":{"decision":"PASS","configuration_digests":{"5":"old-cfg"}}})
    require_package(session, "p", export_result={"expert_loop":{"decision":"PASS","configuration_digests":{"5":"new-cfg"}}})


@pytest.mark.parametrize("invalid", [True, -1, "synthetic-non-numeric-private-canary", {"secret":"synthetic"}, None])
def test_public_token_metadata_contains_only_actual_nonnegative_integers(invalid):
    from zhigou_toolchain.modeling.delivery.trace import MODEL_SCOPE, model_response
    from zhigou_toolchain.modeling.five_stage.expert_runtime import usage_summary
    scope = {"usage":{}}
    token = MODEL_SCOPE.set(scope)
    try:
        model_response({"usage":{"prompt_tokens":invalid,"completion_tokens":7},"choices":[]})
    finally:
        MODEL_SCOPE.reset(token)
    assert scope["usage"] == {"output_tokens":7}
    report = usage_summary([{"physical_call_id":"real-request-id","usage":scope["usage"]}])
    assert report["totals"]["input_tokens"] is None
    assert report["known_subtotal"] == {"input_tokens":0,"output_tokens":7}


def test_oscillation_ignores_program_receipt_timing():
    from zhigou_toolchain.modeling.five_stage.expert_runtime import ExpertRuntime
    version = default_configuration(1)
    version.update(status="CONFIRMED", confirmed_by="synthetic")
    version["configuration"]["coverage_confirmed"] = True
    runtime = ExpertRuntime({"1":version}, guard=lambda: None, sources={"rule:0":{"text":"source"}}, client_factory=lambda: None)
    count = {"produce":0, "review":0}
    def produce(_):
        count["produce"] += 1
        value = {"scope":{"version":count["produce"] % 2},"program_receipt":{"elapsed":count["produce"]}}
        runtime.observe({"method_id":"1.3","tool_id":"scope.validate"}, {"source":"source"}, value)
        return value
    def ask(method, purpose, context, schema, *, evidence):
        if purpose == "REVISE":
            return {"proposal":{"base_digest":context["base_digest"],"changes":[],"unresolved":[]}}
        count["review"] += 1
        return {"proposal":{"decision":"REVISE","summary":"synthetic","checks":[{"criterion_id":c["criterion_id"],"status":"PASS","reason":"synthetic","evidence_refs":[next(iter(evidence))]} for c in version["configuration"]["criteria"]],
            "issues":[{"issue_id":"i","criterion_id":"S1.1","severity":"BLOCKING","location":"scope.description","description":"synthetic","suggestion":"synthetic","target_stage":1,"evidence_refs":["rule:0"]}]}}
    runtime.ask = ask
    _, result = runtime.run(produce, lambda *args: {"changes":[]})
    assert result["stop_reason"] == "EXPERT_OSCILLATION_OR_NO_CHANGE"
    assert count == {"produce":3,"review":2}


def test_patch_cannot_redirect_an_issue_to_another_field():
    from zhigou_toolchain.services.modeling_expert import validate_patch
    patch = {"changes":[{"target":"scope","field":"description","value":"new","issue_id":"i","evidence_ref":"s","quote":"new","quote_start":0}]}
    with pytest.raises(ValueError, match="LOCATION"):
        validate_patch({"scope":{"description":"old"}}, patch,
                       [{"issue_id":"i","target_stage":1,"location":"scope.out_of_scope","evidence_refs":["s"]}],
                       {"s":{"text":"new"}}, "modeling.scope")


def test_business_identity_is_same_across_s4_report_and_rebuilt_proposal():
    from zhigou_toolchain.modeling.five_stage.expert_runtime import business_fingerprint
    candidate = {"candidate_id":"original-origin-id","candidate_kind":"ABOX","candidate_action":"ASSERT",
                 "body":{"literal":{"lexical_value":"same"}},"evidence_refs":["s"],"kg_ir_item_refs":["item"]}
    initial = {"five_stage":{"artifacts":[{"ref":{"step_id":"3.6"},"content":[candidate]}]},"program_timing":1}
    rebuilt = {"proposal":{"abox_candidates":[{**candidate,"candidate_id":"new-origin-id"}],"tbox_candidates":[]},"program_timing":2}
    assert business_fingerprint(initial) == business_fingerprint(rebuilt)


def test_declared_generation_ambiguity_cannot_be_overridden_by_model_pass():
    from zhigou_toolchain.modeling.five_stage.expert_runtime import program_passed
    assert not program_passed("structure.design", {"proposal":{"unresolved":["missing evidence"]}})
    assert not program_passed("scope.suggest", {"five_stage":{"artifacts":[{
        "ref":{"step_id":"1.3"},"content":{"proposal":{"unresolved":["identity unknown"]}}}]}})


def test_failed_interrupted_token_projection_needs_no_candidate_commit():
    from zhigou_toolchain.modeling.five_stage.coverage import token_view
    def event(cid, phase, **extra):
        return {"call_id":cid,"phase":phase,"binding":{"capture_configuration":{}},
                "metadata":{"kind":"MODEL","stage_id":2,"method_id":"2.5", "expert_binding":{"purpose":"GENERATE","loop_id":"loop"}, **extra}}
    events = [event("failed", "BEFORE"), event("failed", "AFTER", status="FAILED", dispatch_status="TRANSPORT_ATTEMPTED", usage={"input_tokens":10,"output_tokens":2}),
              event("retry", "BEFORE"), event("retry", "AFTER", status="SUCCEEDED", dispatch_status="TRANSPORT_ATTEMPTED", usage={"input_tokens":11,"output_tokens":3}),
              event("local", "BEFORE"), event("local", "AFTER", status="FAILED", dispatch_status="NOT_SENT_LOCAL_FAILURE"), event("interrupted", "BEFORE")]
    result = token_view(events + events)
    assert result["physical_calls"] == 2
    assert result["known_subtotal"] == {"input_tokens":21,"output_tokens":5}
    assert result["totals"] == {"input_tokens":None,"output_tokens":None}
    assert result["unconfirmed_dispatch_call_ids"] == ["interrupted"]
    assert result["not_sent_call_ids"] == ["local"]
    trace = {"events":[{"event":"llm_call","call_id":"transport-id","audit_call_id":"interrupted"},
                       {"event":"llm_output","call_id":"transport-id","usage":{"input_tokens":4,"output_tokens":1}}]}
    recovered = token_view(events, trace)
    assert recovered["known_subtotal"] == {"input_tokens":25,"output_tokens":6}
    assert recovered["totals"] == {"input_tokens":None,"output_tokens":None}
