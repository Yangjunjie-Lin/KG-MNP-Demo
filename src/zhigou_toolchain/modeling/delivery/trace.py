"""Opt-in content observations, separate from authoritative jobs and hash audit."""
from __future__ import annotations

import json
import os
import re
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import UTC, datetime
from functools import wraps
from time import perf_counter
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from zhigou_toolchain.contracts.canonical import semantic_hash

from .evolution import HARNESS_KEYS, validate_events
from .exchange_io import atomic_file, checked_path, digest, json_bytes, require

ACTIVE_TRACE: ContextVar[TraceRecorder | None] = ContextVar("ontology_content_trace", default=None)
MODEL_SCOPE: ContextVar[dict | None] = ContextVar("ontology_model_trace_scope", default=None)
CALL_LINK: ContextVar[dict | None] = ContextVar("ontology_call_link", default=None)
PRIVATE_KEYS = {"negative_case_plan", "negative_case_results", "authorization", "cookie", "set-cookie", "api_key", "apikey", "access_token", "password",
                "reasoning_content", "reasoning", "analysis", "acceptance", "expected", "expected_answers",
                "independent_expected_answers", "corrected_answer", "gold", "oracles", "scenario_acceptance", "scenario_quality"}


def public_value(value, changes, path="$", _depth=0):
    """Post-capture filtering is explicitly REDACTED, never called lossless."""
    if _depth > 64:
        changes.add(path + ".depth_limit")
        return "[REDACTED_DEPTH_LIMIT]"
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if str(key).lower() in PRIVATE_KEYS:
                changes.add(path + "." + str(key))
                result[key] = "[REDACTED]"
            else:
                result[key] = public_value(child, changes, path + "." + str(key), _depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [public_value(child, changes, path + "[]", _depth + 1) for child in value]
    if isinstance(value, str):
        # JSON may be nested inside messages.content or source/error quotations.
        # Preserve original bytes when no filtering is needed. Quoted private
        # keys in non-JSON prose fail closed for the whole string (not replayable).
        if value.lstrip().startswith(("{", "[", '"')):
            try:
                decoded = json.loads(value)
            except (ValueError, RecursionError):
                decoded = None
            if isinstance(decoded, (dict, list, str)):
                nested = set()
                safe = public_value(decoded, nested, path + ".json", _depth + 1)
                if nested:
                    changes.update(nested)
                    return json.dumps(safe, ensure_ascii=False)
        if re.search(r'["\'](?:' + "|".join(re.escape(k) for k in PRIVATE_KEYS) + r')["\']\s*:', value, re.IGNORECASE):
            changes.add(path + ".private_quoted_material")
            return "[REDACTED_PRIVATE_QUOTED_MATERIAL]"
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
            next_turn = self.turn + (1 if kind == "llm" else 0)
            call_id = uuid4().hex
            row = self._emit(kind + "_call", turn=next_turn or None, call_id=call_id, **fields)
            self.turn = next_turn
            self.pending[call_id] = (kind, row, perf_counter())
            return call_id

    def result(self, call_id, value, *, error=None, usage=None, public_response=None, local_validation=None):
        with self.lock:
            kind, call, clock = self.pending.pop(call_id)
            fields = {"call_id": call_id, "turn": call["turn"] if kind == "llm" else self.turn or None,
                      "status": "error" if error else "ok", "duration_ms": (perf_counter() - clock) * 1000}
            if error:
                fields["error"] = error
            if kind == "llm":
                fields["content"] = value
                if local_validation is not None:
                    fields["local_validation"] = local_validation
                if public_response is not None:
                    fields["public_response"] = public_response
                if usage:
                    fields["usage"] = {k: v for k, v in usage.items() if type(v) is int and v >= 0}
            else:
                fields.update(tool=call["tool"], result=value)
            return self._emit("llm_output" if kind == "llm" else "tool_result", **fields)

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
        return deepcopy({"format": "zhigou-local-trace/1.0.0", "capture_status": "REDACTED" if self.changes else "COMPLETE",
                "redactions": sorted(self.changes), "events": list(self.events), "bindings": self.bindings,
                "harness_manifest": self.harness,
                "protocol": validate_events(self.events, self.bindings["transport_run_id"], producer=True)})


def traced_proposal(function):
    """One inference event at transport entry; local rejection belongs to its output."""
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any):
        from zhigou_toolchain.modeling.five_stage.audit import ACTIVE_AUDIT
        from zhigou_toolchain.modeling.five_stage.expert_runtime import ACTIVE_EXPERT
        from zhigou_toolchain.modeling.five_stage.prompts import prompt_reference
        from zhigou_toolchain.modeling.five_stage.tools import ToolBlocked
        context = args[2] if len(args) > 2 else kwargs["context"]
        expert = ACTIVE_EXPERT.get()
        expert_binding = None
        original_task = args[1] if len(args) > 1 else kwargs["task"]
        if expert is not None:
            task, context, expert_binding = expert.prepare_prompt(original_task, context, (CALL_LINK.get() or {}).get("method_id"))
            positional: list[Any] = list(args)
            for index, key, value in ((1, "task", task), (2, "context", context)):
                if len(positional) > index:
                    positional[index] = value
                else:
                    kwargs[key] = value
            args = tuple(positional)
        input_changes = set()
        public_value(context, input_changes)
        if input_changes:
            # This happens BEFORE health checks / inference. Filtering the log
            # after sending a forbidden answer would not repair the boundary.
            raise ToolBlocked("MODEL_PRIVATE_INPUT_FORBIDDEN")
        recorder = ACTIVE_TRACE.get()
        audit = ACTIVE_AUDIT.get()
        if recorder is None and audit is None and expert is None:
            return function(*args, **kwargs)
        client = args[0] if args else kwargs["self"]
        if expert is not None:
            from time import monotonic

            import httpx
            client.max_output_tokens = min(client.max_output_tokens, expert.budget["max_output_tokens"])
            remaining = max(0.001, expert.budget["max_seconds"] - (monotonic() - expert.started))
            client.client.timeout = httpx.Timeout(min(45, remaining))
        task, schema = args[1] if len(args) > 1 else kwargs["task"], args[3] if len(args) > 3 else kwargs["schema"]
        scope = {"recorder": recorder, "audit": audit, "call_id": None, "audit_call_id": None,
            "content": "", "usage": {}, "prompt": prompt_reference(task, client, schema),
            "schema": deepcopy(schema), "task": task, "link": CALL_LINK.get() or {},
            "execution_mode": "MOCK_TRANSPORT" if getattr(client, "is_mock_transport", False) else "LIVE",
            "clock": perf_counter()}
        scope["physical_call_id"] = uuid4().hex
        scope["expert_binding"] = expert_binding
        if expert_binding is not None:
            scope["prompt"]["base_task_reference"] = prompt_reference(original_task, client, schema)
            scope["prompt"]["expert_binding"] = expert_binding
        token = MODEL_SCOPE.set(scope)
        error = None
        try:
            result = function(*args, **kwargs)
            scope["validation"] = "LOCAL_SCHEMA_AND_REFERENCE_CHECKS_PASSED"
            return result
        except BaseException as exc:
            label = str(exc)
            error = {"type": type(exc).__name__, "code": label if re.fullmatch(r"[A-Z][A-Z0-9_]{1,100}", label) else None}
            scope["validation"] = {"status": "REJECTED_OR_TRANSPORT_FAILED", "diagnostic": getattr(client, "last_rejection", None)}
            raise
        finally:
            try:
                if scope["call_id"]:
                    assert recorder is not None
                    output_event = recorder.result(scope["call_id"], scope["content"], error=error or scope.get("transport_error"), usage=scope["usage"], public_response=scope.get("public_response"), local_validation=scope.get("validation"))
                    if scope.get("witness") is not None:
                        scope["witness"]["transport_output_event_sha256"] = semantic_hash(output_event)
                if scope["audit_call_id"]:
                    assert audit is not None
                    witness = scope["witness"]
                    witness["dispatch_status"] = "TRANSPORT_ATTEMPTED" if scope.get("dispatched") else "NOT_SENT_LOCAL_FAILURE"
                    witness["audit_after_sha256"] = audit.after(scope["audit_call_id"],
                        {"public_response_sha256": semantic_hash(scope.get("public_response", scope["content"])),
                         "content_sha256": semantic_hash(scope["content"]), "local_validation_sha256": semantic_hash(scope.get("validation"))},
                        status="FAILED" if error else "SUCCEEDED", outcome={
                            "local_validation": scope.get("validation", "REJECTED_OR_TRANSPORT_FAILED"),
                            "dispatch_status": witness["dispatch_status"],
                            "duration_ms": (perf_counter() - scope.get("dispatch_clock", scope["clock"])) * 1000,
                            "usage": scope["usage"], "expert_binding": expert_binding,
                            "error": error, "transport_error": scope.get("transport_error")})
            finally:
                if expert is not None:
                    expert.physical_result(scope, error)
                MODEL_SCOPE.reset(token)
    return wrapped


def model_request(payload):
    from zhigou_toolchain.modeling.five_stage.expert_runtime import ACTIVE_EXPERT
    expert = ACTIVE_EXPERT.get()
    if expert is not None:
        expert.before_request(payload)
    scope = MODEL_SCOPE.get()
    if scope is not None:
        require(scope["call_id"] is None and scope["audit_call_id"] is None, "MODEL_RETRY_REQUIRES_NEW_PROPOSAL_SCOPE")
        link = scope["link"]
        association = {k: link.get(k) for k in ("native_agent_run_id", "parent_audit_call_id", "parent_transport_call_id", "method_id", "stage_id", "actor", "tool_id")}
        identities = {"request_sha256": semantic_hash(payload), "messages_sha256": semantic_hash(payload["messages"]),
            "schema_sha256": semantic_hash(scope["schema"]), "prompt": scope["prompt"],
            "execution_mode": scope["execution_mode"], **association}
        if scope.get("expert_binding"):
            identities["expert_binding"] = scope["expert_binding"]
        audit = scope["audit"]
        if audit is not None:
            configured = audit.binding.get("capture_configuration", {})
            message_capture = "TRACE_CHANNEL" if scope["recorder"] else "NOT_AUTHORIZED" if (
                configured.get("model_trace_enabled") and not configured.get("record_authorized")) else "NOT_RECORDED_TRACE_DISABLED"
            scope["audit_call_id"] = audit.before({"kind": "MODEL", **identities,
                "messages_capture": message_capture},
                {"request_sha256": identities["request_sha256"]})
            scope["witness"] = {"audit_call_id": scope["audit_call_id"],
                "audit_before_sha256": audit.calls[scope["audit_call_id"]]["before_event_sha256"], **identities}
            if "model_calls" in link:
                link["model_calls"].append(scope["witness"])
        if scope["recorder"] is None:
            return
        if scope["execution_mode"] == "MOCK_TRANSPORT":
            scope["recorder"].bindings["execution_mode"] = "MOCK_TRANSPORT"
        fields = {"messages": payload["messages"], "model": payload["model"],
                  "request_parameters": {k: v for k, v in payload.items() if k != "messages"},
                  "task": scope["task"], "output_schema": scope["schema"], **identities,
                  "audit_call_id": scope["audit_call_id"],
                  "unspecified_parameters": [k for k in ("temperature", "top_p", "seed", "reasoning_effort", "max_tokens", "max_completion_tokens") if k not in payload]}
        if "temperature" in payload:
            fields["temperature"] = payload["temperature"]
        scope["call_id"] = scope["recorder"].call("llm", **fields)
        if audit is not None:
            scope["witness"]["transport_call_id"] = scope["call_id"]
            scope["witness"]["transport_run_id"] = scope["recorder"].bindings["transport_run_id"]
            scope["witness"]["transport_request_event_sha256"] = semantic_hash(scope["recorder"].pending[scope["call_id"]][1])


def model_dispatched():
    """Transport attempt, not proof of server receipt; excludes local log gates."""
    scope = MODEL_SCOPE.get()
    if scope is not None:
        scope.update(dispatched=True, dispatch_clock=perf_counter())


def model_response(response, *, http_status=None, request_id=None):
    scope = MODEL_SCOPE.get()
    if scope is None:
        return
    if isinstance(response, dict):
        choices = response.get("choices", [])
        scope["public_response"] = {"model": response.get("model"), "id": response.get("id"),
            "http_request_id": request_id,
            "provider_request_id": response.get("request_id"), "usage": response.get("usage"),
            "system_fingerprint": response.get("system_fingerprint"),
            "choices": [{"finish_reason": c.get("finish_reason"), "message": {k: v for k, v in c["message"].items()
                if k in {"role", "content", "refusal", "tool_calls"}}} for c in choices
                if isinstance(c, dict) and isinstance(c.get("message"), dict)] if isinstance(choices, list) else []}
        scope["content"] = [c.get("message", {}).get("content") for c in choices
                            if isinstance(c, dict) and isinstance(c.get("message"), dict)] if isinstance(choices, list) else []
        if len(scope["content"]) == 1:
            scope["content"] = scope["content"][0]
        if not isinstance(choices, list) or not choices or any(not isinstance(c, dict) or not isinstance(c.get("message"), dict) for c in choices):
            scope["content"] = {"malformed_public_envelope": response}
        if "error" in response:
            scope["content"] = {"public_error": response["error"]}
        usage = response.get("usage") or {}
        if isinstance(usage, dict):
            scope["usage"] = {dst: usage[src] for src, dst in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens"))
                              if type(usage.get(src)) is int and usage[src] >= 0}
    else:
        scope["content"] = response
    if http_status is not None and http_status >= 400:
        scope["transport_error"] = {"http_status": http_status}


def partial_model_response(reason):
    scope = MODEL_SCOPE.get()
    if scope is not None and scope["recorder"] is not None:
        scope["recorder"].changes.add("$.transport." + reason)
