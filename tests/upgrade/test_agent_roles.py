from copy import deepcopy

import pytest

from zhigou_toolchain.modeling.five_stage.agents import (
    ACTIVE,
    AgentRun,
    AgentToolDenied,
    RuleAgent,
    TaskExecutionAgent,
    invoke,
)


def test_two_roles_really_execute_only_their_stage_tools():
    run = AgentRun("session", "task", None, [])
    rule, task = RuleAgent(run), TaskExecutionAgent(run)
    value = {"input": 1}
    for actor, stage, tool in [(rule, 1, "input.profile"), (rule, 2, "structure.design"),
                               (task, 3, "facts.normalize"), (rule, 4, "semantic.check"), (task, 5, "compile.build")]:
        previous = deepcopy(value)
        value = actor.execute(stage, tool, lambda v=previous: {"parent": v}, inputs=previous)
    assert [r["agent_id"] for r in run.records] == ["RuleAgent", "RuleAgent", "TaskExecutionAgent", "RuleAgent", "TaskExecutionAgent"]
    assert [r["stage_id"] for r in run.records] == [1, 2, 3, 4, 5]
    assert all(r["status"] == "SUCCEEDED" and r["output_sha256"] and r["ended_at"] for r in run.records)
    assert run.report()["approval"] == "NOT_GRANTED"


@pytest.mark.parametrize("actor,stage,tool", [(RuleAgent, 3, "records.map"), (TaskExecutionAgent, 2, "structure.retrieve"),
    (RuleAgent, 4, "review.action"), (RuleAgent, 4, "benchmark.score"), (TaskExecutionAgent, 5, "release.publish"),
    (TaskExecutionAgent, 5, "read_file"), (TaskExecutionAgent, 5, "task.execute")])
def test_denial_precedes_side_effect(actor, stage, tool):
    touched = []
    run = AgentRun("s", "t", None, [])
    with pytest.raises(AgentToolDenied):
        actor(run).execute(stage, tool, lambda: touched.append(True), inputs={})
    assert touched == []
    assert len(run.records) == 1
    assert run.records[0]["status"] == "DENIED"
    assert run.records[0]["output_sha256"] is None
    assert run.records[0]["ended_at"]


def test_real_generation_defers_record_mapping_until_structure_is_complete():
    from tests.upgrade.test_model_assistance import RecordedBoundary, context_and_drafts
    from zhigou_toolchain.modeling.five_stage.assistance import generate

    context, drafts = context_and_drafts()
    context["planned_record_mapping"] = {"version": "test-mapping-v1"}
    boundary = RecordedBoundary([
        {"decisions": [], "unresolved": []}, {"additions": [], "unresolved": []},
        {"facts": [], "unresolved": []},
    ])
    run = AgentRun("s", "t", "2", [])

    def mapping():
        assert len(boundary.contexts) == 2  # Actual S2 calls, not UI labels.
        assert boundary.contexts[1]["existing_drafts"] == []
        assert boundary.contexts[1]["planned_record_mapping"] == context["planned_record_mapping"]
        return {"drafts": drafts, "report": {"status": "MAPPED"}}

    token = ACTIVE.set(run)
    try:
        result, receipt = generate(boundary, context=context, initial_drafts=[], record_builder=mapping,
            configuration={"retrieval": "LLM_SUBSTITUTE", "chunking": "UNICODE_SUBSTITUTE"})
    finally:
        ACTIVE.reset(token)
    assert result == drafts and receipt["record_mapping"]["status"] == "MAPPED"
    assert [r["tool_id"] for r in run.records] == ["structure.design", "structure.design", "records.map", "text.chunk", "text.extract"]
    assert [r["stage_id"] for r in run.records] == [2, 2, 3, 3, 3]
    assert boundary.contexts[2]["subjects"] == ["urn:new:A"]


def test_context_is_scoped_and_failure_does_not_expose_source_or_secrets():
    run = AgentRun("s", "t", "parent-v1", [{"identifier": "source", "digest": "abc", "status": "CURRENT"}])
    def fail():
        raise ValueError("secret-bearing provider error")
    token = ACTIVE.set(run)
    try:
        with pytest.raises(ValueError):
            invoke(1, "input.profile", fail, inputs={"source": "private material"})
    finally:
        ACTIVE.reset(token)
    assert run.records[0]["status"] == "FAILED"
    assert run.records[0]["reason"] == "ValueError"
    assert "secret-bearing" not in str(run.report()) and "private material" not in str(run.report())
    assert ACTIVE.get() is None


def test_actual_worker_retains_computation_audit_when_fenced_publication_fails(tmp_path, monkeypatch):
    from pathlib import Path

    from tests.services.test_modeling_workflow import call
    from zhigou_toolchain.jobs.worker import JobWorker
    from zhigou_toolchain.services import execution
    from zhigou_toolchain.services.facade import ApplicationService
    from zhigou_toolchain.services.models import OperationRequest, ServiceConfiguration
    from zhigou_toolchain.services.projects import get_project

    service = ApplicationService(ServiceConfiguration(str(tmp_path)))
    _, principal = service.tokens.create(principal_id="synthetic-human", principal_type="HUMAN", permissions={"*"}, project_ids=set(), created_by="test")
    project = service.execute(OperationRequest("project.create", parameters={"name": "agent audit", "domain_pack": "minimal", "domain_pack_version": "0.1.0"}), principal).payload["project_id"]
    seeded = call(service, principal, project, "modeling.tutorial.seed", {}, "seed")
    before = get_project(service.root, project)
    digest = execution.tree_digest(Path(before.root))
    service.execute(OperationRequest("modeling.profile", project, {"run_id": seeded["run"]["run_id"]}, "audit-profile"), principal)

    def fail_catalog(*args):
        raise OSError("Synthetic publication failure")

    monkeypatch.setattr(execution, "save_catalog", fail_catalog)
    result = JobWorker(service.jobs, service).run_once("audit-worker")
    assert result.status == "FAILED"
    audit = result.error["agent_execution"]
    assert audit["publication_status"] == "NOT_CONFIRMED" and audit["approval"] == "NOT_GRANTED"
    assert audit["records"][0]["agent_id"] == "RuleAgent" and audit["records"][0]["tool_id"] == "input.profile"
    assert get_project(service.root, project) == before and execution.tree_digest(Path(before.root)) == digest
