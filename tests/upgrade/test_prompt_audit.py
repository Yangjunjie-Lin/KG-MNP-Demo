"""Synthetic network spies; no LIVE inference or external receiver evidence."""
import json
from copy import deepcopy
from dataclasses import replace

import httpx
import pytest

from tests.services.test_modeling_workflow import call
from tests.upgrade.prompt_spy import CLIENT_TYPES, PromptSpy
from tests.upgrade.test_evolution_delivery import recorder
from tests.upgrade.test_model_assistance import context_and_drafts, patch
from tests.upgrade.test_step_audit import service_case  # noqa: F401
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.delivery.trace import public_value
from zhigou_toolchain.modeling.five_stage.agents import (
    ACTIVE,
    AgentRun,
    RuleAgent,
    invoke,
)
from zhigou_toolchain.modeling.five_stage.assistance import generate, repair
from zhigou_toolchain.modeling.five_stage.audit import ACTIVE_AUDIT, StepAudit
from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
from zhigou_toolchain.modeling.five_stage.coverage import (
    implementation_view,
    reconcile_physical_requests,
)
from zhigou_toolchain.modeling.five_stage.prompts import source_catalogue
from zhigou_toolchain.modeling.five_stage.registry import registry
from zhigou_toolchain.modeling.five_stage.tools import ModelLock, ToolBlocked
from zhigou_toolchain.services.modeling_audit import (
    audit_detail,
    audit_root,
    download_audit,
    read_events,
)


@pytest.mark.parametrize("value", [
    {"messages": [{"content": json.dumps({"nested": {"corrected_answer": "PRIVATE_CANARY"}})}]},
    {"quote": 'example = {"expected_answers": "PRIVATE_CANARY"}'},
    {"error": 'source {"api_key": "PRIVATE_CANARY"}'},
    {"content": json.dumps({"nested": json.dumps({"corrected_answer": "PRIVATE_CANARY"})})},
])
def test_serialized_private_material_is_not_public_content(value):
    changes = set()
    assert "PRIVATE_CANARY" not in json.dumps(public_value(value, changes))
    assert changes


def test_physical_model_request_is_linked_even_without_message_capture(tmp_path):
    observed = []
    def handler(request):
        observed.append(json.loads(request.content))
        return httpx.Response(200, json={"model": "synthetic", "choices": [
            {"finish_reason": "stop", "message": {"content": '{"value":"ok"}'}}]})
    client = CompatibleClient(ModelLock("synthetic", "mock-r1", "http://localhost/v1"),
        transport=httpx.MockTransport(handler))
    audit = StepAudit(tmp_path, {"job_id": "synthetic"}, content=True)
    run = AgentRun("session", "task", "1", [])
    token = ACTIVE_AUDIT.set(audit)
    try:
        RuleAgent(run).execute(2, "structure.design", lambda: client.propose("Synthetic", {},
            {"type": "object", "properties": {"value": {"type": "string"}}}), inputs={})
    finally:
        ACTIVE_AUDIT.reset(token)
        client.close()
    events = [json.loads(p.read_bytes()) for p in sorted(tmp_path.glob("*.json"))]
    physical = [e for e in events if e["phase"] == "BEFORE" and e["metadata"]["kind"] == "MODEL"]
    assert len(physical) == len(observed) == 1
    assert physical[0]["metadata"]["parent_audit_call_id"] == events[0]["call_id"]
    assert physical[0]["metadata"]["messages_capture"] == "NOT_RECORDED_TRACE_DISABLED"
    assert run.records[0]["model_calls"][0]["audit_call_id"] == physical[0]["call_id"]


@pytest.mark.parametrize("client_type", CLIENT_TYPES)
def test_real_builders_two_rounds_chunks_repair_and_independent_accounting(tmp_path, client_type):
    context, drafts = context_and_drafts()
    spy = PromptSpy(client_type=client_type, responses=[{"decisions": [], "unresolved": []},
        {"additions": [], "unresolved": []}, {"facts": [], "unresolved": []},
        {"patches": [patch()], "unresolved": []}])
    client, trace = spy.client(), recorder()
    audit, run = StepAudit(tmp_path, {"job_id": "synthetic"}, content=True), AgentRun("session", "task", "1", [])
    at, rt = ACTIVE_AUDIT.set(audit), ACTIVE.set(run)
    try:
        with trace.activate():
            generate(client, context=context, initial_drafts=drafts, configuration={"retrieval": "LLM_SUBSTITUTE", "chunking": "UNICODE_SUBSTITUTE"})
            invoke(3, "facts.repair", lambda: repair(client, original_drafts=drafts, context=context, issues={}, configuration={}), inputs={})
    finally:
        ACTIVE.reset(rt)
        ACTIVE_AUDIT.reset(at)
        client.close()
    snapshot = trace.finish("success", {})
    events = [json.loads(p.read_bytes()) for p in sorted(tmp_path.glob("*.json"))]
    assert reconcile_physical_requests([r["request"] for r in spy.requests], events, snapshot)["physical_requests"] == 4
    assert [r["method_id"] for r in spy.requests] == ["2.4", "2.5", "3.3", "4.3"]
    calls = [e for e in snapshot["events"] if e["event"] == "llm_call"]
    assert all(c["prompt"]["template_status"] == "SOURCE_MATCHED" for c in calls)
    assert snapshot["bindings"]["execution_mode"] == "MOCK_TRANSPORT"
    assert snapshot["protocol"]["status"] == "BLOCKED"  # real pre-model tool turn
    for captured, actual in zip(calls, spy.requests, strict=True):
        assert captured["messages"] == actual["request"]["messages"]
        assert captured["request_sha256"] == semantic_hash(actual["request"])
        assert captured["schema_sha256"] == semantic_hash(captured["output_schema"])
        assert captured["prompt"]["task_sha256"] == semantic_hash(captured["task"])
    if client_type is CompatibleClient:
        assert all("temperature" in c["unspecified_parameters"] for c in calls)
        assert all("JSON schema:" in c["messages"][0]["content"] for c in calls)
    else:
        assert spy.health_requests == 4
        assert all(c["request_parameters"]["structured_outputs"]["json"] == c["output_schema"] for c in calls)
        assert all("JSON schema:" not in c["messages"][0]["content"] for c in calls)
    missing = deepcopy(snapshot)
    missing["events"].remove(next(e for e in missing["events"] if e["event"] == "llm_call"))
    with pytest.raises(ValueError, match="PHYSICAL_CALL_COUNT_MISMATCH"):
        reconcile_physical_requests([r["request"] for r in spy.requests], events, missing)
    missing_method = [e for e in events if e["call_id"] != calls[0]["audit_call_id"]]
    with pytest.raises(ValueError, match="PHYSICAL_CALL_COUNT_MISMATCH"):
        reconcile_physical_requests([r["request"] for r in spy.requests], missing_method, snapshot)
    # Returned snapshots are immutable observations of the earlier capture.
    snapshot["events"][0]["task_input"]["query"] = "modified"
    assert trace.snapshot()["events"][0]["task_input"]["query"] == "fixture"


def test_registry_and_catalogue_are_complete_source_views():
    assert {m["method_id"] for m in implementation_view()} == {m["method_id"] for m in registry()["methods"]}
    catalogue = source_catalogue()
    main = [t for t in catalogue["templates"] if t["group"] == "PRODUCTION" and t["task_text"] is not None]
    assert len(main) == 5
    assert "services/modeling_five_stage.py" in catalogue["source_files"]
    assert {t["group"] for t in catalogue["templates"]} == {"PRODUCTION", "RESEARCH_ADAPTER", "EXPERT_RUNTIME", "EXPERT_DEFAULT_DRAFT_NOT_HUMAN_CONFIRMATION", "SCENARIO_FROZEN_CONFIGURATION"}
    assert len([t for t in catalogue["templates"] if t["group"] == "EXPERT_DEFAULT_DRAFT_NOT_HUMAN_CONFIRMATION"]) == 11
    from zhigou_toolchain.modeling.five_stage.scenarios import (
        SCENARIO_GENERATE_PROMPT,
        SCENARIO_REVIEW_PROMPT,
        SCENARIO_REVISE_PROMPT,
    )
    scene_templates = [t for t in catalogue["templates"] if t["group"] == "SCENARIO_FROZEN_CONFIGURATION"]
    assert len(scene_templates) == 3
    assert {t["task_text"] for t in scene_templates} == {SCENARIO_GENERATE_PROMPT, SCENARIO_REVIEW_PROMPT, SCENARIO_REVISE_PROMPT}
    scene_ids = {s["scenario_id"] for s in catalogue["scenario_resources"]}
    assert scene_ids == {"organization_management", "ancient_tree_inspection", "equipment_maintenance"}
    assert all("modeling/five_stage/resources/scenarios/" + identifier + ".json" in catalogue["source_files"] for identifier in scene_ids)
    assert "scenario_acceptance" not in json.dumps(catalogue["scenario_resources"])
    assert all(t["context_expression"] and t["schema_expression"] for t in main)


def test_catalogue_documents_are_generated_from_the_executing_sources():
    from pathlib import Path

    from zhigou_toolchain.modeling.five_stage.prompts import markdown
    root = Path(__file__).resolve().parents[2] / "docs/ontology"
    catalogue = source_catalogue()
    assert json.loads((root / "MODEL_CALL_PROMPTS.json").read_bytes()) == catalogue
    assert (root / "MODEL_CALL_PROMPTS.md").read_text(encoding="utf-8") == markdown(catalogue)


def test_invalid_method_is_rejected_before_computation():
    run = AgentRun("session", "task", "1", [])
    with pytest.raises(ValueError, match="AGENT_TOOL_METHOD_MISMATCH"):
        RuleAgent(run).execute(2, "structure.design", lambda: pytest.fail("must not execute"), inputs={}, method_id="1.2")


@pytest.mark.parametrize("step_content,model_content", [(False, False), (False, True), (True, False), (True, True)])
def test_scope_internal_profile_and_separate_capture_switches(service_case, monkeypatch, step_content, model_content):  # noqa: F811
    service, principal, _, project, seed = service_case
    service.configuration = replace(service.configuration, modeling_audit_content_enabled=step_content, ontology_trace_enabled=model_content)
    spy = PromptSpy()
    monkeypatch.setattr("zhigou_toolchain.services.modeling_five_stage.configured_client", spy.client)
    result = call(service, principal, project, "modeling.scope.draft", {"run_id": seed["run"]["run_id"],
        "business_goal": "Synthetic goal", "business_rules": ["Do not infer rules"]}, "scope-prompt")
    assert [s["step_id"] for s in result["five_stage"]["step_runs"]] == ["1.1", "1.2", "1.3"]
    job = service.jobs.list_project(project)[0]
    detail = audit_detail(service, principal, project, job.job_id)
    events = detail["events"]
    assert len([e for e in events if e["phase"] == "BEFORE" and e["metadata"].get("tool_id") == "data.profile"]) == 1
    assert (detail["actual_model_trace"] is not None) == model_content
    if model_content:
        reconcile_physical_requests([r["request"] for r in spy.requests], events, detail["actual_model_trace"])
    assert all(e["payload"]["capture"] == "METADATA_ONLY" for e in events) == (not step_content)
    assert detail["archive_sha256"] == __import__("hashlib").sha256(download_audit(service, principal, project, job.job_id)).hexdigest()


@pytest.mark.parametrize("client_type", CLIENT_TYPES)
@pytest.mark.parametrize("failure", ["http", "timeout", "json", "schema", "refusal", "list"])
def test_failed_physical_request_survives_validation_and_retry(tmp_path, client_type, failure):
    if failure == "http":
        response = httpx.Response(503, json={"error": "synthetic-unavailable"})
    elif failure == "timeout":
        response = httpx.ReadTimeout("Bearer PRIVATE_CANARY")
    else:
        response = httpx.Response(200, json=[] if failure == "list" else {"model": "synthetic-model", "choices": [{
            "finish_reason": "stop", "message": {"content": "not-json" if failure == "json" else '{"value":42}' if failure == "schema" else '{"value":"ok"}',
                **({"refusal": "synthetic refusal"} if failure == "refusal" else {})}}]})
    spy = PromptSpy(client_type=client_type, responses=[response, {"value": "ok"}])
    client, trace = spy.client(), recorder()
    audit, run = StepAudit(tmp_path, {"job_id": "synthetic"}), AgentRun("session", "task", "1", [])
    at = ACTIVE_AUDIT.set(audit)
    schema = {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}
    try:
        with trace.activate():
            with pytest.raises(ToolBlocked):
                RuleAgent(run).execute(2, "structure.design", lambda: client.propose("Synthetic", {}, schema), inputs={})
            RuleAgent(run).execute(2, "structure.design", lambda: client.propose("Synthetic", {}, schema), inputs={})
    finally:
        ACTIVE_AUDIT.reset(at)
        client.close()
    snapshot = trace.finish("success", {})
    events = [json.loads(p.read_bytes()) for p in sorted(tmp_path.glob("*.json"))]
    reconcile_physical_requests([r["request"] for r in spy.requests], events, snapshot)
    outputs = [e for e in snapshot["events"] if e["event"] == "llm_output"]
    assert [e["status"] for e in outputs] == ["error", "ok"]
    assert [e["turn"] for e in outputs] == [1, 2]
    assert "PRIVATE_CANARY" not in json.dumps(snapshot)


def test_private_serialized_input_rejected_before_any_network():
    spy = PromptSpy()
    client = spy.client()
    try:
        with pytest.raises(ToolBlocked, match="MODEL_PRIVATE_INPUT_FORBIDDEN"):
            client.propose("Synthetic", {"source": '{"nested":{"corrected_answer":"PRIVATE_CANARY"}}'}, {"type": "object"})
    finally:
        client.close()
    assert spy.requests == [] and spy.health_requests == 0


def test_post_commit_audit_failure_does_not_invent_rollback(service_case, monkeypatch):  # noqa: F811
    service, principal, _, project, seed = service_case
    original = StepAudit.after
    def fail_after_commit(self, call_id, *args, **kwargs):
        if kwargs["status"] == "COMMITTED":
            raise OSError("PRIVATE_CANARY")
        return original(self, call_id, *args, **kwargs)
    monkeypatch.setattr(StepAudit, "after", fail_after_commit)
    result = call(service, principal, project, "modeling.profile", {"run_id": seed["run"]["run_id"]}, "post-commit-error")
    job = service.jobs.list_project(project)[0]
    assert job.status == "SUCCEEDED" and job.result == result
    detail = audit_detail(service, principal, project, job.job_id)
    assert detail["manifest"]["commit_status"] == "COMMITTED"
    assert detail["manifest"]["pair_status"] == "INTERRUPTED"
    assert not any(e["metadata"].get("status") == "COMMITTED" for e in read_events(service, job))


def test_recomputed_chain_cannot_reassign_model_method_parent_prompt_or_attempt(service_case, monkeypatch):  # noqa: F811
    service, principal, _, project, seed = service_case
    spy = PromptSpy()
    monkeypatch.setattr("zhigou_toolchain.services.modeling_five_stage.configured_client", spy.client)
    call(service, principal, project, "modeling.scope.draft", {"run_id": seed["run"]["run_id"],
        "business_goal": "Synthetic", "business_rules": ["Preserve source evidence"]}, "tamper-model")
    job = service.jobs.list_project(project)[0]
    directory = audit_root(service, project, job.job_id, job.attempt)
    paths = sorted(directory.glob("??????-*.json"))
    originals = [p.read_bytes() for p in paths]
    for field, bad in [("method_id", "5.5"), ("parent_audit_call_id", "wrong-parent"), ("request_sha256", "0" * 64), ("prompt", {})]:
        rows = [json.loads(raw) for raw in originals]
        model = next(e for e in rows if e["phase"] == "BEFORE" and e["metadata"]["kind"] == "MODEL")
        model["metadata"][field] = bad
        previous = None
        for path, row in zip(paths, rows, strict=True):
            row["previous_event_sha256"] = previous
            row["event_sha256"] = semantic_hash({k: v for k, v in row.items() if k != "event_sha256"})
            previous = row["event_sha256"]
            path.write_text(json.dumps(row), encoding="utf-8")
        with pytest.raises(ValueError, match="STEP_AUDIT_.*MISMATCH"):
            download_audit(service, principal, project, job.job_id)
        for path, raw in zip(paths, originals, strict=True):
            path.write_bytes(raw)
    changed = json.loads(originals[0])
    changed["binding"]["attempt"] += 1
    changed["event_sha256"] = semantic_hash({k: v for k, v in changed.items() if k != "event_sha256"})
    paths[0].write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="STEP_AUDIT_BINDING_INVALID"):
        download_audit(service, principal, project, job.job_id)


def test_two_concurrent_requests_keep_separate_parent_ids_and_out_of_order_results(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context
    from threading import Barrier, Event
    barrier, second_done, observed = Barrier(2), Event(), []
    def handler(request):
        payload = json.loads(request.content)
        observed.append(payload)
        value = json.loads(payload["messages"][1]["content"])["slot"]
        barrier.wait(timeout=10)
        if value == 0:
            assert second_done.wait(timeout=10)
        else:
            second_done.set()
        return httpx.Response(200, json={"model": "synthetic", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"slot": value})}}]})
    trace, run = recorder(), AgentRun("session", "task", "1", [])
    audit = StepAudit(tmp_path, {"job_id": "concurrency"})
    at = ACTIVE_AUDIT.set(audit)
    def task(slot):
        client = CompatibleClient(ModelLock("synthetic", "mock-r1", "http://localhost/v1"), transport=httpx.MockTransport(handler))
        try:
            return RuleAgent(run).execute(2, "structure.design", lambda: client.propose("Synthetic", {"slot": slot}, {"type": "object"}), inputs={"slot": slot})
        finally:
            client.close()
    try:
        with trace.activate(), ThreadPoolExecutor(max_workers=2) as pool:
            pending = [pool.submit(copy_context().run, task, slot) for slot in range(2)]
            assert [p.result()["proposal"]["slot"] for p in pending] == [0, 1]
    finally:
        ACTIVE_AUDIT.reset(at)
    snapshot = trace.finish("success", {})
    events = [json.loads(p.read_bytes()) for p in sorted(tmp_path.glob("*.json"))]
    reconcile_physical_requests(observed, events, snapshot)
    calls = [e for e in snapshot["events"] if e["event"] == "llm_call"]
    assert len({c["parent_audit_call_id"] for c in calls}) == len({c["call_id"] for c in calls}) == 2


def test_json_schema_mode_parameters_and_source_template_never_replace_capture():
    spy = PromptSpy(responses=[{"value": "ok"}], response_format="json_schema", reasoning_effort="low")
    trace, client = recorder(), spy.client()
    schema = {"type": "object", "properties": {"value": {"type": "string"}}, "additionalProperties": False, "required": ["value"]}
    try:
        with trace.activate():
            client.propose("External dynamic task", {}, schema)
    finally:
        client.close()
    snapshot = trace.finish("success", {})
    call = next(e for e in snapshot["events"] if e["event"] == "llm_call")
    assert call["prompt"]["template_status"] == "DYNAMIC_OR_EXTERNAL_TASK"
    assert call["request_parameters"]["response_format"]["json_schema"]["schema"] == schema
    assert call["request_parameters"]["reasoning_effort"] == "low"
    assert "max_tokens" not in call["request_parameters"]
    assert call["request_parameters"]["max_completion_tokens"] == 8192


def test_trace_content_tamper_cannot_hide_behind_redacted_status(service_case, monkeypatch):  # noqa: F811
    from zhigou_toolchain.modeling.delivery.exchange_io import json_bytes
    from zhigou_toolchain.services.ontology_traces import trace_root
    service, principal, _, project, seed = service_case
    service.configuration = replace(service.configuration, ontology_trace_enabled=True)
    spy = PromptSpy()
    monkeypatch.setattr("zhigou_toolchain.services.modeling_five_stage.configured_client", spy.client)
    result = call(service, principal, project, "modeling.scope.draft", {"run_id": seed["run"]["run_id"],
        "business_goal": "Synthetic", "business_rules": ["Preserve evidence"]}, "trace-tamper")
    job = service.jobs.list_project(project)[0]
    path = trace_root(service, project, job.job_id, job.attempt) / (result["agent_execution"]["run_id"].split(":")[-1] + ".jsonl.json")
    trace = json.loads(path.read_bytes())
    next(e for e in trace["events"] if e["event"] == "llm_output")["content"] = "FORGED_RESULT"
    trace["capture_status"] = "REDACTED"
    path.write_bytes(json_bytes(trace))
    path.with_suffix(".tmp").write_bytes(b"".join(json_bytes(e) for e in trace["events"]))
    with pytest.raises(ValueError, match="STEP_TRACE_CAPTURE_CHANGED"):
        download_audit(service, principal, project, job.job_id)


def test_local_trace_limit_is_not_counted_as_a_sent_request(tmp_path, monkeypatch):
    spy, trace = PromptSpy(responses=[{}]), recorder()
    client, run = spy.client(), AgentRun("session", "task", "1", [])
    audit = StepAudit(tmp_path, {"job_id": "limit"})
    original = trace._emit
    def bounded(event, **fields):
        if event == "llm_call":
            raise ValueError("TRACE_LIMIT")
        return original(event, **fields)
    monkeypatch.setattr(trace, "_emit", bounded)
    at = ACTIVE_AUDIT.set(audit)
    try:
        with trace.activate(), pytest.raises(ValueError, match="TRACE_LIMIT"):
            RuleAgent(run).execute(2, "structure.design", lambda: client.propose("Synthetic", {}, {"type": "object"}), inputs={})
    finally:
        ACTIVE_AUDIT.reset(at)
        client.close()
    assert trace.turn == 0 and spy.requests == []
    events = [json.loads(p.read_bytes()) for p in sorted(tmp_path.glob("*.json"))]
    snapshot = trace.finish("failed", {})
    reconcile_physical_requests([], events, snapshot)
    assert next(e for e in events if e["metadata"]["kind"] == "MODEL" and e["phase"] == "AFTER")["metadata"]["dispatch_status"] == "NOT_SENT_LOCAL_FAILURE"
