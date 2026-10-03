"""Independent MockTransport observes actual requests of both original clients."""
import json

import httpx
import pytest

from zhigou_toolchain.modeling.five_stage.expert import default_configuration
from zhigou_toolchain.modeling.five_stage.scenarios import SCENES, resolve


@pytest.mark.parametrize("scene", SCENES)
@pytest.mark.parametrize("stage", range(1, 6))
@pytest.mark.parametrize("qwen", [False, True])
def test_same_frozen_scene_enters_generation_review_and_revision(tmp_path, scene, stage, qwen):
    from zhigou_toolchain.modeling.five_stage.agents import ACTIVE, AgentRun, invoke
    from zhigou_toolchain.modeling.five_stage.audit import ACTIVE_AUDIT, StepAudit
    from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
    from zhigou_toolchain.modeling.five_stage.expert_runtime import (
        ACTIVE_EXPERT,
        ExpertRuntime,
    )
    from zhigou_toolchain.modeling.five_stage.tools import ModelLock, QwenClient
    configuration = resolve({"scenario_id": scene, "scenario_version": "2.0.0"})
    version = default_configuration(stage)
    version.update(status="CONFIRMED", version=1, confirmed_by="synthetic-test",
        scenario_stage_digest=configuration["stage_digests"][f"S{stage}"])
    version["configuration"]["coverage_confirmed"] = True
    spy = []
    def transport(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "mock"}]})
        spy.append(json.loads(request.content))
        return httpx.Response(200, json={"model": "mock", "choices": [{"message": {"content": '{"value":"source-bound"}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2}})
    def factory():
        return (QwenClient if qwen else CompatibleClient)(ModelLock("mock", "v1", "https://synthetic.invalid/v1"), transport=httpx.MockTransport(transport))
    runtime = ExpertRuntime({str(stage): version}, guard=lambda: None, sources={}, client_factory=factory, scenario=configuration)
    audit = StepAudit(tmp_path, {"job_id": "synthetic-scene-requests"})
    at, rt, et = ACTIVE_AUDIT.set(audit), ACTIVE.set(AgentRun("s", "t", "1", [])), ACTIVE_EXPERT.set(runtime)
    tool = {1: "scope.suggest", 2: "structure.design", 3: "text.extract", 4: "repair.route", 5: "compile.plan"}[stage]
    method = {1: "1.3", 2: "2.5", 3: "3.3", 4: "4.3", 5: "5.1"}[stage]
    schema = {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"], "additionalProperties": False}
    client = factory()
    try:
        invoke(stage, tool, lambda: client.propose("Existing instruction", {"source": "authorized"}, schema), inputs={}, method_id=method)
        for purpose in ("REVIEW", "REVISE"):
            runtime.ask(method, purpose, {"source": "authorized"}, schema, evidence=set())
    finally:
        client.close()
        ACTIVE_EXPERT.reset(et)
        ACTIVE.reset(rt)
        ACTIVE_AUDIT.reset(at)
    assert len(spy) == len(runtime.calls) == 3
    bodies = [json.loads(r["messages"][1]["content"]) for r in spy]
    assert [b["expert_binding"]["purpose"] for b in bodies] == ["GENERATE", "REVIEW", "REVISE"]
    assert all(b["scenario_context"]["effective_configuration_digest"] == configuration["digest"] for b in bodies)
    assert all(b["scenario_context"]["stage_configuration_digest"] == version["scenario_stage_digest"] for b in bodies)
    additions = configuration["stages"][f"S{stage}"]["expert_additions"]
    assert additions["pre_guidance"] in spy[0]["messages"][0]["content"]
    assert additions["post_review"] in spy[1]["messages"][0]["content"]
    assert all(text in spy[2]["messages"][0]["content"] for text in additions.values())
    assert all("level" not in b["scenario_context"]["effective_stage_config"] for b in bodies)
    assert all(c["scenario_id"] == scene and c["usage"] == {"input_tokens": 5, "output_tokens": 2} for c in runtime.calls)


def test_nested_revalidation_error_cannot_be_overridden_by_method_or_model_pass():
    from tests.upgrade.expert_spy import ExpertSpy
    from zhigou_toolchain.modeling.five_stage.agents import ACTIVE, AgentRun
    from zhigou_toolchain.modeling.five_stage.expert_runtime import (
        ACTIVE_EXPERT,
        ExpertRuntime,
    )
    version = default_configuration(4)
    version.update(status="CONFIRMED", version=1, confirmed_by="synthetic")
    version["configuration"]["coverage_confirmed"] = True
    spy = ExpertSpy()
    runtime = ExpertRuntime({"4": version}, guard=lambda: None, sources={}, client_factory=spy.client)
    def produce(_):
        runtime.observe({"method_id": "4.1", "tool_id": "integrity.check", "audit_call_id": "synthetic-local-receipt"}, {}, {"status": "PASS"})
        return {"automatic_validation": {"status": "ERROR", "code": "SYNTHETIC_UNAVAILABLE_VALIDATOR"}}
    token, agent = ACTIVE_EXPERT.set(runtime), ACTIVE.set(AgentRun("synthetic", "synthetic", "1", []))
    try:
        _, report = runtime.run(produce, lambda *_: {})
    finally:
        ACTIVE_EXPERT.reset(token)
        ACTIVE.reset(agent)
    assert report["decision"] == "ESCALATE"
    assert report["rounds"][0]["overall_program_passed"] is False
