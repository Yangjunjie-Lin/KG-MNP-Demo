"""Credential-free engineering replay through the actual generation/kernel entry.

Only ENGINEERING_CHECK inputs are accepted. This is not LIVE inference, not a
way to convert gold into benchmark predictions, and never a research score.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import yaml
from jsonschema import validate
from pydantic import Field

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.tools import validate_references

from .contracts import Closed, ModelingInput, Protocol
from .engine import generate_sample
from .provenance import source_identity


class Recording(Closed):
    model_id: str
    declared_revision: str
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replies: list[dict] = Field(min_length=1, max_length=20)


class RecordedProposalClient:
    execution_mode = "RECORDED"
    def __init__(self, recording, protocol):
        self.recording = recording
        self.index = 0
        self.lock = SimpleNamespace(model_id=recording.model_id, revision=recording.declared_revision)
        self.reasoning_effort = protocol.reasoning_effort
        self.last_public_response = None

    def propose(self, instruction, content, schema, *, allowed_iris=()):
        from zhigou_toolchain.modeling.delivery.trace import ACTIVE_TRACE
        trace = ACTIVE_TRACE.get()
        call_id = trace.call("tool", tool="recording.replay", args={"instruction": instruction, "content": content, "schema": schema}) if trace else None
        try:
            return self._replay(instruction, content, schema, allowed_iris=allowed_iris)
        except BaseException as exc:
            if trace and call_id:
                trace.result(call_id, {}, error={"type": type(exc).__name__})
            raise
        finally:
            if trace and call_id and call_id in trace.pending:
                trace.result(call_id, self.recording.replies[self.index - 1])

    def _replay(self, instruction, content, schema, *, allowed_iris=()):
        if self.index >= len(self.recording.replies):
            raise ValueError("ENGINEERING_RECORDING_EXHAUSTED")
        value = self.recording.replies[self.index]
        self.index += 1
        validate(value, schema)
        validate_references(value, set(allowed_iris), set())
        return {"proposal": value, "execution_source": "RECORDED", "model": {"model_id": self.recording.model_id},
            "request": {"instruction": instruction, "content": content, "schema": schema},
            "usage": {"total_tokens": None}, "authority": "ENGINEERING_FIXTURE_ONLY", "live_inference_calls": 0}


def replay_sample(input_path, protocol_path, recording_path, output, *, system, record_trace=False):
    sample = ModelingInput.model_validate_json(Path(input_path).read_bytes())
    protocol = Protocol.model_validate(yaml.safe_load(Path(protocol_path).read_text(encoding="utf-8")))
    recording = Recording.model_validate_json(Path(recording_path).read_bytes())
    if sample.evaluation_scope != "ENGINEERING_CHECK":
        raise ValueError("REPLAY_ONLY_ACCEPTS_ENGINEERING_INPUTS")
    if recording.input_sha256 != semantic_hash(sample.model_dump(mode="json")):
        raise ValueError("REPLAY_FROZEN_INPUT_CHANGED")
    if (recording.model_id, recording.declared_revision) != (protocol.model_id, protocol.declared_revision):
        raise ValueError("REPLAY_MODEL_CONTEXT_CHANGED")
    client = RecordedProposalClient(recording, protocol)
    identity = source_identity(Path(__file__).resolve().parents[3])
    result = generate_sample(sample, protocol, system, Path(output), client=client, record_trace=record_trace)
    unchanged = source_identity(Path(__file__).resolve().parents[3]) == identity
    report = {"status": result["status"] if unchanged else "INVALID_SOURCE_CHANGED", "execution_mode": "RECORDED_ENGINEERING_ONLY", "live_inference_calls": 0,
        "logical_provider_calls": len(result["calls"]), "recorded_replies_consumed": client.index,
        "unused_recorded_replies": len(recording.replies) - client.index, "research_score": None,
        "recording_sha256": semantic_hash(recording.model_dump(mode="json")), "result_sha256": semantic_hash(result),
        "input_sha256": recording.input_sha256, "protocol_sha256": semantic_hash(protocol.model_dump(mode="json")),
        "source_commit": identity["commit"], "source_fingerprint_sha256": identity["fingerprint"]["digest"], "source_unchanged": unchanged,
        "output": str(output), "approval": "NOT_GRANTED", "release_status": "NOT_RELEASED"}
    (Path(output) / "replay-receipt.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
