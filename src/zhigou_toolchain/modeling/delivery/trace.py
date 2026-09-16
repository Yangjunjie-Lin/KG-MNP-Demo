"""Opt-in content observations, separate from authoritative jobs and hash audit."""
from __future__ import annotations

import json
import os
import re
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import wraps
from time import perf_counter
from uuid import NAMESPACE_URL, uuid4, uuid5

from .evolution import HARNESS_KEYS, validate_events
from .exchange_io import atomic_file, checked_path, digest, json_bytes, require

ACTIVE_TRACE: ContextVar[TraceRecorder | None] = ContextVar("ontology_content_trace", default=None)
MODEL_SCOPE: ContextVar[dict | None] = ContextVar("ontology_model_trace_scope", default=None)
PRIVATE_KEYS = {"authorization", "cookie", "set-cookie", "api_key", "apikey", "access_token", "password",
                "reasoning_content", "reasoning", "analysis", "acceptance", "expected", "expected_answers",
                "independent_expected_answers", "corrected_answer", "gold", "oracles"}


def public_value(value, changes, path="$"):
    """Post-capture filtering is explicitly REDACTED, never called lossless."""
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if str(key).lower() in PRIVATE_KEYS:
                changes.add(path + "." + str(key))
                result[key] = "[REDACTED]"
            else:
                result[key] = public_value(child, changes, path + "." + str(key))
        return result
    if isinstance(value, (list, tuple)):
        return [public_value(child, changes, path + "[]") for child in value]
    if isinstance(value, str):
        cleaned = re.sub(r"(?i)(?:https?://)[^\s\"<>]+[?@][^\s\"<>]*", "[REDACTED_SECRET_URL]", value)
        cleaned = re.sub(r"(?i)(?:bearer\s+|sk-)[A-Za-z0-9._-]+", "[REDACTED_CREDENTIAL]", cleaned)
        cleaned = re.sub(r'(?i)((?:api[_-]?key|authorization|cookie|password)\s*[=:]\s*)[^\s,;]+', r'\1[REDACTED]', cleaned)
        if cleaned != value:
            changes.add(path)
        return cleaned
    if value is None or type(value) in {int, float, bool}:
        return value
    changes.add(path)
    return {"unserializable_type": type(value).__name__, "capture": "PARTIAL"}


def freeze_harness(resources, *, provenance):
    require(set(resources) == set(HARNESS_KEYS), "SIX_HARNESS_RESOURCES_REQUIRED")
    redactions = set()
    safe_resources = public_value(resources, redactions, "$.harness")
    if not isinstance(safe_resources, dict):
        raise TypeError("HARNESS_RESOURCES_MUST_BE_OBJECT")
    safe_provenance = public_value(provenance, redactions, "$.provenance")
    frozen = {key: json.loads(json_bytes(safe_resources[key])) for key in HARNESS_KEYS}
    hashes = {key: digest(json_bytes(frozen[key])) for key in HARNESS_KEYS}
    return {"algorithm": "SHA256_UTF8_SORTED_KEYS_COMPACT_JSON_WITH_LF_V1", "hashes": hashes,
            "resources": frozen, "provenance": safe_provenance, "redactions": sorted(redactions)}


class TraceRecorder:
    def __init__(self, *, native_run_id, task_id, task_input, harness, bindings, journal=None):
        self.lock = threading.RLock()
        self.events = []
        self.pending = {}
        self.turn = 0
        self.changes = set()
        self.started = perf_counter()
        self.harness = harness
        self.changes.update(harness.get("redactions", []))
        self.bindings = {**bindings, "native_agent_run_id": native_run_id,
                         "transport_run_id": uuid5(NAMESPACE_URL, "zhigou:" + native_run_id).hex, "task_id": task_id}
        self.journal = checked_path(journal) if journal else None
        self.finished = False
        if self.journal:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
            atomic_file(self.journal.with_suffix(".context.json"), json_bytes({"bindings": self.bindings, "harness_manifest": self.harness}))
        self._emit("task_start", task_id=task_id, task_input=task_input, harness=harness["hashes"])

    @contextmanager
    def activate(self):
        token = ACTIVE_TRACE.set(self)
        try:
            yield self
        finally:
            ACTIVE_TRACE.reset(token)

    def _emit(self, event, **fields):
        require(not self.finished, "TRACE_ALREADY_FINISHED")
        row = public_value({"event": event, "ts": datetime.now(UTC).isoformat(),
                            "run_id": self.bindings["transport_run_id"], **fields}, self.changes)
        raw = json_bytes(row)
        require(len(raw) <= 4_000_000 and len(self.events) < 10000, "TRACE_LIMIT")
        self.events.append(row)
        if self.journal:
            require(self.journal.stat().st_size + len(raw) <= 64_000_000, "TRACE_LIMIT")
            with self.journal.open("ab") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        return row

    def call(self, kind, **fields):
        with self.lock:
            require(kind in {"llm", "tool"}, "TRACE_CALL_KIND")
            if kind == "llm":
                self.turn += 1
            call_id = uuid4().hex
            row = self._emit(kind + "_call", turn=self.turn or None, call_id=call_id, **fields)
            self.pending[call_id] = (kind, row, perf_counter())
            return call_id

    def result(self, call_id, value, *, error=None, usage=None, public_response=None):
        with self.lock:
            kind, call, clock = self.pending.pop(call_id)
            fields = {"call_id": call_id, "turn": call["turn"] if kind == "llm" else self.turn or None,
                      "status": "error" if error else "ok", "duration_ms": (perf_counter() - clock) * 1000}
            if error:
                fields["error"] = error
            if kind == "llm":
                fields["content"] = value
                if public_response is not None:
                    fields["public_response"] = public_response
                if usage:
                    fields["usage"] = {k: v for k, v in usage.items() if type(v) is int and v >= 0}
            else:
                fields.update(tool=call["tool"], result=value)
            self._emit("llm_output" if kind == "llm" else "tool_result", **fields)

    def finish(self, status, answer, *, error=None):
        with self.lock:
            require(not self.pending, "TRACE_UNCLOSED_CALLS")
            require(status in {"success", "failed", "cancelled"}, "TRACE_STATUS")
            self._emit("task_end", status=status, answer=answer, duration_ms=(perf_counter() - self.started) * 1000,
                       **({"error": error} if error else {}))
            self.finished = True
        snapshot = self.snapshot()
        if self.journal:
            atomic_file(self.journal.with_suffix(".json"), json_bytes(snapshot))
        return snapshot

    def snapshot(self):
        return {"format": "zhigou-local-trace/1.0.0", "capture_status": "REDACTED" if self.changes else "COMPLETE",
                "redactions": sorted(self.changes), "events": list(self.events), "bindings": self.bindings,
                "harness_manifest": self.harness,
                "protocol": validate_events(self.events, self.bindings["transport_run_id"], producer=True)}


def traced_proposal(function):
    """One inference event at transport entry; local rejection belongs to its output."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        recorder = ACTIVE_TRACE.get()
        if recorder is None:
            return function(*args, **kwargs)
        scope = {"recorder": recorder, "call_id": None, "content": "", "usage": {}}
        token = MODEL_SCOPE.set(scope)
        error = None
        try:
            return function(*args, **kwargs)
        except BaseException as exc:
            label = str(exc)
            error = {"type": type(exc).__name__, "code": label if re.fullmatch(r"[A-Z][A-Z0-9_]{1,100}", label) else None}
            raise
        finally:
            try:
                if scope["call_id"]:
                    recorder.result(scope["call_id"], scope["content"], error=error or scope.get("transport_error"), usage=scope["usage"], public_response=scope.get("public_response"))
            finally:
                MODEL_SCOPE.reset(token)
    return wrapped


def model_request(payload):
    scope = MODEL_SCOPE.get()
    if scope is not None:
        require(scope["call_id"] is None, "MODEL_RETRY_REQUIRES_NEW_PROPOSAL_SCOPE")
        fields = {"messages": payload["messages"], "model": payload["model"],
                  "request_parameters": {k: v for k, v in payload.items() if k != "messages"}}
        if "temperature" in payload:
            fields["temperature"] = payload["temperature"]
        scope["call_id"] = scope["recorder"].call("llm", **fields)


def model_response(response, *, http_status=None):
    scope = MODEL_SCOPE.get()
    if scope is None:
        return
    if isinstance(response, dict):
        choices = response.get("choices", [])
        scope["public_response"] = {"model": response.get("model"), "id": response.get("id"),
            "choices": [{"finish_reason": c.get("finish_reason"), "message": {k: v for k, v in c["message"].items()
                if k in {"role", "content", "refusal", "tool_calls"}}} for c in choices
                if isinstance(c, dict) and isinstance(c.get("message"), dict)] if isinstance(choices, list) else []}
        scope["content"] = [c.get("message", {}).get("content") for c in choices
                            if isinstance(c, dict) and isinstance(c.get("message"), dict)] if isinstance(choices, list) else []
        if len(scope["content"]) == 1:
            scope["content"] = scope["content"][0]
        if "error" in response:
            scope["content"] = {"public_error": response["error"]}
        usage = response.get("usage") or {}
        if isinstance(usage, dict):
            scope["usage"] = {dst: usage[src] for src, dst in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")) if src in usage}
    else:
        scope["content"] = response
    if http_status is not None and http_status >= 400:
        scope["transport_error"] = {"http_status": http_status}


def partial_model_response(reason):
    scope = MODEL_SCOPE.get()
    if scope is not None:
        scope["recorder"].changes.add("$.transport." + reason)
