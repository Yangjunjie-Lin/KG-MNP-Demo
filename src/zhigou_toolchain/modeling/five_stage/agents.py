"""Two computational roles over the existing control plane, never approval authority.

The broker is the only tool surface exposed to these roles. The deterministic
coordinator selects stages; neither role can call approval, publication, business
actions, arbitrary files, or a benchmark scorer. Receipts are job observations,
not another session/candidate/version store.
"""
from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from zhigou_toolchain import __version__
from zhigou_toolchain.contracts.canonical import semantic_hash

OWNERS = {1: "RuleAgent", 2: "RuleAgent", 3: "TaskExecutionAgent", 4: "RuleAgent", 5: "TaskExecutionAgent"}
TOOLS = {
    1: frozenset({"input.profile", "scope.suggest", "scope.validate"}),
    2: frozenset({"baseline.prepare", "structure.retrieve", "structure.rerank", "structure.design"}),
    3: frozenset({"records.map", "text.chunk", "text.extract", "evidence.bind", "facts.normalize", "facts.repair"}),
    4: frozenset({"integrity.check", "semantic.check", "repair.route"}),
    5: frozenset({"compile.plan", "compile.build", "archive.verify", "archive.export", "delivery.v3"}),
}
ACTIVE: ContextVar[AgentRun | None] = ContextVar("ontology_agent_run", default=None)


class AgentToolDenied(ValueError):
    pass


@dataclass
class AgentRun:
    session_id: str
    task_id: str
    parent_version: str | None
    dependencies: list[dict]
    mode: str = "PRODUCTION"
    run_id: str = field(default_factory=lambda: "agent-run:" + uuid4().hex)
    records: list[dict] = field(default_factory=list)

    def call(self, agent_id: str, stage_id: int, tool_id: str, action: Callable[[], Any],
             *, inputs: Any, model: dict | None = None, versions: dict | None = None):
        # Never serialize source values, prompts, credentials or answer content
        # into this audit. Model transports retain only their own permitted logs.
        started = datetime.now(UTC).isoformat()
        clock = perf_counter()
        record = {"schema_version": "1.0.0", "session_id": self.session_id, "run_id": self.run_id,
            "task_id": self.task_id, "stage_id": stage_id, "agent_id": agent_id, "tool_id": tool_id,
            "parent_version": self.parent_version, "dependencies": self.dependencies,
            "input_sha256": semantic_hash(inputs), "output_sha256": None,
            "tool_versions": {"zhigou_toolchain": __version__, **(versions or {})}, "model": model,
            "started_at": started, "status": "RUNNING", "mode": self.mode, "authority": "OBSERVATION_ONLY"}
        self.records.append(record)
        try:
            if OWNERS.get(stage_id) != agent_id or tool_id not in TOOLS.get(stage_id, ()):
                record.update(status="DENIED", reason="AGENT_TOOL_OR_STAGE_FORBIDDEN")
                raise AgentToolDenied("AGENT_TOOL_OR_STAGE_FORBIDDEN")
            value = action()
            record.update(status="SUCCEEDED", output_sha256=semantic_hash(value), reason="Registered tool completed; semantic outcome is in its result")
            if isinstance(value, dict):
                if isinstance(value.get("tool_versions"), dict):
                    record["tool_versions"].update(value["tool_versions"])
                if isinstance(value.get("model"), dict) and value.get("execution_source") in {"LIVE", "RECORDED"}:
                    record["model"] = {k: v for k, v in value["model"].items() if k in {
                        "model_id", "configured_revision", "observed_model_id", "revision_attestation"}}
            return value
        except Exception as exc:
            if record["status"] != "DENIED":
                record.update(status="FAILED", reason=type(exc).__name__)
            raise
        finally:
            record.update(ended_at=datetime.now(UTC).isoformat(), duration_seconds=perf_counter() - clock)

    def report(self):
        return {"run_id": self.run_id, "session_id": self.session_id, "task_id": self.task_id,
            "mode": self.mode, "authority": "OBSERVATION_ONLY", "records": self.records,
            "approval": "NOT_GRANTED", "release_status": "NOT_RELEASED"}


class RuleAgent:
    agent_id = "RuleAgent"

    def __init__(self, run: AgentRun):
        self.run = run

    def execute(self, stage: int, tool: str, action, *, inputs, model=None, versions=None):
        return self.run.call(self.agent_id, stage, tool, action, inputs=inputs, model=model, versions=versions)


class TaskExecutionAgent(RuleAgent):
    agent_id = "TaskExecutionAgent"


class FiveStageCoordinator:
    """In-memory sequencing, not a second production session authority."""
    def __init__(self, run: AgentRun):
        self.run = run
        self.next_stage = 1
        self.parent_digest = None

    def execute(self, stage, tool, action, *, inputs, parent_digest=None):
        if stage != self.next_stage or parent_digest != self.parent_digest:
            raise AgentToolDenied("STAGE_ORDER_OR_HANDOFF_MISMATCH")
        actor = RuleAgent(self.run) if OWNERS[stage] == "RuleAgent" else TaskExecutionAgent(self.run)
        value = actor.execute(stage, tool, action, inputs=inputs)
        self.parent_digest = semantic_hash(value)
        self.next_stage += 1
        return value


def invoke(stage: int, tool: str, action, *, inputs, model=None, versions=None):
    run = ACTIVE.get()
    if run is None:
        # Direct library use is not relabelled as an Agent execution.
        return action()
    actor = RuleAgent(run) if OWNERS.get(stage) == "RuleAgent" else TaskExecutionAgent(run)
    return actor.execute(stage, tool, action, inputs=inputs, model=model, versions=versions)


OPERATION_TO_TOOL = {
    "modeling.profile": (1, "input.profile"), "modeling.scope.draft": (1, "scope.suggest"),
    "modeling.scope": (1, "scope.validate"),
    "modeling.prepare": (2, "baseline.prepare"), "modeling.cq": (2, "baseline.prepare"),
    "modeling.baseline": (2, "baseline.prepare"), "modeling.alignment": (2, "baseline.prepare"),
    "modeling.semantic.check": (4, "semantic.check"),
    "compile.plan": (5, "compile.plan"), "compile.plan.exact": (5, "compile.plan"),
    "compile.build": (5, "compile.build"), "compile.validate": (5, "archive.verify"),
    "compile.reproduce": (5, "compile.build"), "package.verify": (5, "archive.verify"),
    "package.export": (5, "archive.export"),
}


def execute_routed(project, request, action):
    """Called inside the existing Worker generation/CAS transaction.

Human scope/review decisions deliberately do not appear as Agent tool calls.
The proposal handler records fine-grained S2/S3/S4 calls itself.
"""
    from zhigou_toolchain.services.modeling_sessions import read
    if request.operation_id not in OPERATION_TO_TOOL and request.operation_id not in {"modeling.proposal", "modeling.candidate"}:
        return action()
    session = read(project.root)
    run = AgentRun(session_id=session["session_id"] if session else "legacy-session:" + project.project_id,
        task_id=request.idempotency_key, parent_version=str(session["revision"]) if session else None,
        dependencies=[{k: o[k] for k in ("identifier", "digest", "status")} for o in (session or {}).get("outputs", []) if o["status"] != "STALE"])
    token = ACTIVE.set(run)
    try:
        if request.operation_id in OPERATION_TO_TOOL:
            stage, tool = OPERATION_TO_TOOL[request.operation_id]
            result = invoke(stage, tool, action, inputs=request.parameters)
        else:
            result = action()
        return {**result, "agent_execution": run.report()}
    except Exception as exc:
        setattr(exc, "agent_execution", run.report())  # noqa: B010 - arbitrary tool exception types
        raise
    finally:
        ACTIVE.reset(token)
