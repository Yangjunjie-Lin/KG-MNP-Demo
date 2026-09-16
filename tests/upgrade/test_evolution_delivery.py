from __future__ import annotations

import json
from copy import deepcopy

import httpx
import pytest

from zhigou_toolchain.modeling.delivery.evolution import (
    HARNESS_KEYS,
    evolution_files,
    export_batch,
    parse_jsonl,
    validate_batch,
    validate_events,
    validate_review,
)
from zhigou_toolchain.modeling.delivery.exchange_io import digest, json_bytes
from zhigou_toolchain.modeling.delivery.trace import TraceRecorder, freeze_harness
from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
from zhigou_toolchain.modeling.five_stage.tools import (
    ModelLock,
    QwenClient,
    ToolBlocked,
)


def recorder(tmp_path=None):
    harness = freeze_harness({k: {"resource": k, "content": "synthetic fixture"} for k in HARNESS_KEYS}, provenance={"mode": "SYNTHETIC_MOCK"})
    return TraceRecorder(native_run_id="agent-run:test", task_id="synthetic-test", task_input={"query": "fixture"}, harness=harness,
        bindings={"execution_mode": "SYNTHETIC_MOCK"}, journal=tmp_path / "run.jsonl.tmp" if tmp_path else None)


def valid_trace():
    r = recorder()
    first = r.call("llm", messages=[{"role": "user", "content": "synthetic"}])
    a = r.call("tool", tool="same", args={"slot": 1})
    b = r.call("tool", tool="same", args={"slot": 2})
    r.result(first, "public")
    second = r.call("llm", messages=[])
    r.result(b, {}, error={"type": "SyntheticError"})
    r.result(a, {"ok": True})
    r.result(second, "retry result")
    return r.finish("success", {"kind": "synthetic-result"})


def test_pairing_parallel_cross_turn_and_idempotent_export(tmp_path):
    trace = valid_trace()
    assert trace["protocol"]["status"] == "LOCAL_PROTOCOL_VALID"
    files = evolution_files([trace], batch_id="synthetic-b1", deliverer="engineering-test")
    assert validate_batch(files, producer=True)["status"] == "LOCAL_PROTOCOL_VALID"
    assert not any(n.startswith("reviews/") for n in files)
    assert export_batch(tmp_path / "batch", files)["status"] == "EXPORTED"
    assert export_batch(tmp_path / "batch", files)["status"] == "ALREADY_EXPORTED"
    with pytest.raises(ValueError, match="DUPLICATE_RUN_DELIVERY"):
        export_batch(tmp_path / "another-batch", files)
    bad = {**files, "context/changed.json": b"{}"}
    with pytest.raises(ValueError, match="IDEMPOTENCY"):
        export_batch(tmp_path / "batch", bad)
    for name, raw in files.items():
        if name.startswith("executions/"):
            broken = {**files, name: raw + b" "}
            with pytest.raises(ValueError, match="BYTES_MISMATCH"):
                validate_batch(broken)


@pytest.mark.parametrize("mutation,code", [
    (lambda e: e[1].update(turn=2), "LLM_TURN_SEQUENCE"),
    (lambda e: e[1].update(ts="2026-09-16T00:00:00"), "TIMEZONE_REQUIRED"),
    (lambda e: e[1].update(run_id="other"), "RUN_ID_MISMATCH"),
    (lambda e: e[3].update(call_id=e[2]["call_id"]), "DUPLICATE_CALL_ID"),
    (lambda e: e[4].update(call_id="absent"), "ORPHAN_RESULT"),
    (lambda e: e[4].update(turn=5), "RESULT_PAIR_MISMATCH"),
])
def test_invalid_trace_rejected(mutation, code):
    trace = valid_trace()
    events = deepcopy(trace["events"])
    mutation(events)
    result = validate_events(events, trace["bindings"]["transport_run_id"], producer=True)
    assert code in {e["code"] for e in result["errors"]}


def test_program_steps_cannot_be_fabricated_and_crash_stays_incomplete(tmp_path):
    r = recorder(tmp_path)
    call = r.call("tool", tool="program", args={})
    assert (tmp_path / "run.jsonl.tmp").is_file()
    assert (tmp_path / "run.jsonl.context.json").is_file()
    assert not (tmp_path / "run.jsonl.json").exists()
    assert "UNCLOSED_PAIR" in {e["code"] for e in r.snapshot()["protocol"]["errors"]} or r.pending
    r.result(call, {})
    trace = r.finish("cancelled", {}, error={"type": "ConfirmedCancellation"})
    assert not any(e["event"] == "llm_call" for e in trace["events"])
    with pytest.raises(ValueError, match="PRE_MODEL"):
        evolution_files([trace], batch_id="program", deliverer="test")


@pytest.mark.parametrize("client_type", [CompatibleClient, QwenClient])
@pytest.mark.parametrize("response_kind", ["ok", "http", "json", "schema", "invalid_envelope", "refusal"])
def test_actual_transport_success_failure_and_public_responses(client_type, response_kind):
    content = '{"value": 1}' if response_kind not in {"json", "schema"} else "not json" if response_kind == "json" else '{"value":"bad"}'
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "synthetic-model"}]})
        if response_kind == "http":
            return httpx.Response(503, json={"error": {"message": "synthetic unavailable"}})
        if response_kind == "invalid_envelope":
            return httpx.Response(200, content=b"truncated")
        return httpx.Response(200, json={"model": "synthetic-model", "choices": [{"finish_reason": "stop", "message": {
            "content": content if response_kind != "refusal" else None, "refusal": "public refusal" if response_kind == "refusal" else None,
            "reasoning_content": "PRIVATE_NOT_FOR_EXPORT"}}]})
    r = recorder()
    client = client_type(ModelLock("synthetic-model", "synthetic-v1", "http://127.0.0.1:1/v1"), transport=httpx.MockTransport(handler), api_key="SYNTHETIC_SECRET")
    try:
        with r.activate():
            if response_kind == "ok":
                client.propose("synthetic task", {}, {"type": "object", "properties": {"value": {"type": "integer"}}})
            else:
                with pytest.raises(ToolBlocked):
                    client.propose("synthetic task", {}, {"type": "object", "properties": {"value": {"type": "integer"}}})
    finally:
        client.close()
    trace = r.finish("success" if response_kind == "ok" else "failed", {})
    assert [e["event"] for e in trace["events"]] == ["task_start", "llm_call", "llm_output", "task_end"]
    output = trace["events"][2]
    assert output["status"] == ("ok" if response_kind == "ok" else "error")
    assert "usage" not in output
    assert "PRIVATE_NOT_FOR_EXPORT" not in json.dumps(trace) and "SYNTHETIC_SECRET" not in json.dumps(trace)
    if response_kind == "refusal":
        assert output["public_response"]["choices"][0]["message"]["refusal"] == "public refusal"


def test_original_warnings_and_stricter_producer():
    trace = valid_trace()
    for row in trace["events"]:
        row.pop("call_id", None)
    report = validate_events(trace["events"], trace["bindings"]["transport_run_id"])
    assert "CALL_ID_MISSING" in {e["code"] for e in report["warnings"]}
    row = {"review_id": "r", "exec_id": "run", "verdict": "fail", "annotations": [], "reviewer": "synthetic", "ts": "2026-09-16T00:00:00+00:00"}
    assert validate_review(row, {"run"})["warnings"] == ["FAIL_ANNOTATIONS_MISSING"]
    assert validate_review(row, {"run"}, producer=True)["errors"] == ["FAIL_ANNOTATIONS_MISSING"]
    with pytest.raises(ValueError, match="JSONL"):
        parse_jsonl(b'{"event":')
    assert digest(json_bytes({"a": "中文"}))


def test_tool_failure_retry_concurrency_and_redaction():
    from concurrent.futures import ThreadPoolExecutor

    from zhigou_toolchain.modeling.five_stage.agents import AgentRun
    trace = recorder()
    run = AgentRun("synthetic-session", "synthetic-task", None, [])
    model = trace.call("llm", messages=[])
    trace.result(model, "public")
    def action(slot):
        with trace.activate():
            return run.call("RuleAgent", 2, "structure.retrieve", lambda: {"slot": slot}, inputs={"slot": slot})
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(v["slot"] for v in pool.map(action, range(12))) == list(range(12))
    with trace.activate():
        def failed():
            raise RuntimeError("secret provider text")
        with pytest.raises(RuntimeError):
            run.call("RuleAgent", 2, "structure.retrieve", failed, inputs={})
        run.call("RuleAgent", 2, "structure.retrieve", lambda: {"retried": True}, inputs={})
    result = trace.finish("success", {})
    assert result["protocol"]["status"] == "LOCAL_PROTOCOL_VALID"
    assert "secret provider text" not in json.dumps(result)
    trace = recorder()
    call = trace.call("llm", messages=[{"role": "user", "content": "Bearer SECRET_VALUE https://host/path?token=secret"}])
    trace.result(call, "public")
    result = trace.finish("success", {})
    assert result["capture_status"] == "REDACTED" and "SECRET_VALUE" not in json.dumps(result)
    with pytest.raises(ValueError, match="REDACTED_OR_PARTIAL"):
        evolution_files([result], batch_id="redacted", deliverer="test")


@pytest.mark.parametrize("name", ["../escape", "/abs", "C:/drive", "file:stream", "a\\b", "a/../b", "CON", "x\u0000y", "a.", "x?"])
def test_paths_are_rejected(name):
    from zhigou_toolchain.modeling.delivery.exchange_io import safe_name
    with pytest.raises(ValueError, match="UNSAFE"):
        safe_name(name)


@pytest.mark.parametrize("change", ["missing", "length", "hash", "path", "duplicate"])
def test_manifest_rejects_whole_batch(change):
    files = evolution_files([valid_trace()], batch_id="negative-batch", deliverer="test")
    manifest = json.loads(files["upstream_manifest.json"])
    row = manifest["files"][0]
    if change == "missing":
        files.pop(row["name"])
    elif change == "length":
        row["size"] += 1
    elif change == "hash":
        row["sha256"] = "0" * 64
    elif change == "path":
        row["name"] = "../escape.jsonl"
    else:
        manifest["files"].append(row)
    files["upstream_manifest.json"] = json_bytes(manifest)
    with pytest.raises(ValueError):
        validate_batch(files)


def test_recorded_provider_is_not_mislabeled_as_deterministic():
    from zhigou_toolchain.services.handoff import execution_mode
    invocation = {"provider_type": "RECORDED_EXTERNAL_MODEL", "determinism_class": "RECORDED_BYTES_ONLY"}
    assert execution_mode({}, []) == "DETERMINISTIC"
    assert execution_mode({}, [invocation]) == "RECORDED"
    assert execution_mode({"execution_source": "RECORDED"}, []) == "RECORDED"
    assert execution_mode({"execution_source": "LIVE"}, [invocation]) == "LIVE"
