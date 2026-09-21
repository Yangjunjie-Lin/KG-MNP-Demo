"""Only configured model transport is callable; no arbitrary URLs or tools."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.compatible import (
    CompatibleClient,
    configured_client,
)

from .live_budget import BudgetLedger


def dispatch(request, *, protocol, ledger: BudgetLedger, job_id, request_id, directory, endpoint_sha256=None, timeout=150, code=None):
    if set(request) != {"instruction", "content", "schema", "allowed_iris"}:
        raise ValueError("MODEL_BROKER_REQUEST_FIELDS_FORBIDDEN")
    def deny_references(value, depth=0):
        if depth > 40:
            raise ValueError("BROKER_SCHEMA_DEPTH_LIMIT")
        if isinstance(value, dict):
            if {"$ref", "$dynamicRef", "$recursiveRef"} & value.keys():
                raise ValueError("BROKER_SCHEMA_EXTERNAL_REFERENCE_FORBIDDEN")
            for child in value.values():
                deny_references(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                deny_references(child, depth + 1)
    deny_references(request["schema"])
    reserve = (len(json.dumps(request["content"], ensure_ascii=False).encode()) + len(request["instruction"].encode())
        + len(json.dumps(request["schema"]).encode()) + 2048 + protocol.budget.max_output_tokens)
    if reserve > protocol.budget.context_window_tokens:
        raise ValueError("BROKER_CONTEXT_BOUND_EXCEEDED")
    if len(json.dumps(request["content"], ensure_ascii=False)) > protocol.budget.max_input_characters:
        raise ValueError("BROKER_INPUT_CHARACTERS_EXCEEDED")
    client = configured_client()
    try:
        if not isinstance(client, CompatibleClient):
            raise TypeError("BROKER_REQUIRES_EXPLICIT_COMPATIBLE_TRANSPORT")
        if client.lock.model_id != protocol.model_id or client.lock.revision != protocol.declared_revision:
            raise ValueError("BROKER_CONFIGURED_MODEL_CHANGED")
        if getattr(client, "reasoning_effort", None) != protocol.reasoning_effort:
            raise ValueError("BROKER_REASONING_CONFIG_CHANGED")
        actual_endpoint = semantic_hash(client.lock.location)
        if endpoint_sha256 is not None and actual_endpoint != endpoint_sha256:
            raise ValueError("BROKER_ENDPOINT_CHANGED")
        if protocol.request_profile is None:
            raise ValueError("BROKER_FROZEN_REQUEST_PROFILE_REQUIRED")
        client.configure_request_profile(**protocol.request_profile.model_dump(mode="json"))
        client.max_output_tokens = protocol.budget.max_output_tokens
        ledger.reserve(request_id, job_id, reserve)
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=False)
        (path / "request.json").write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        if code is not None:
            env["PYTHONPATH"] = str(Path(code).resolve())
        command = {"request": request, "protocol": protocol.model_dump(mode="json"), "endpoint_sha256": actual_endpoint}
        try:
            process = subprocess.run([sys.executable, "-m", "zhigou_toolchain.ontology_io.transport_worker"],
                input=json.dumps(command, ensure_ascii=False).encode(), capture_output=True, timeout=max(1, timeout), env=env, check=False)
            response = json.loads(process.stdout) if process.returncode == 0 else {"ok": False, "error_code": "TRANSPORT_PROCESS_FAILED"}
        except subprocess.TimeoutExpired:
            response = {"ok": False, "error_code": "TRANSPORT_WALLTIME_EXCEEDED"}
        except (ValueError, OSError):
            response = {"ok": False, "error_code": "TRANSPORT_PROCESS_RESPONSE_INVALID"}
        status = "SUCCEEDED" if response["ok"] else "FAILED"
        # Rejected JSON/schema/refusal responses still carry provider usage.
        # Never let semantic acceptance determine whether a call is charged.
        metadata = response.get("receipt") or response.get("public_response") or {}
        counters = metadata.get("usage") or {}
        usage = counters.get("total_tokens")
        completion = counters.get("completion_tokens")
        if completion is not None and (type(completion) is not int or completion < 0 or completion > protocol.budget.max_output_tokens):
            status = "USAGE_BOUND_VIOLATION"
        if metadata.get("invalid_usage_fields") or any(type(v) is not int or v < 0 for v in counters.values()):
            status = "USAGE_BOUND_VIOLATION"
        if usage is not None and (type(usage) is not int or usage < 0):
            usage = None  # Invalid counts are not known usage (and never zero).
        (path / "response.json").write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
        ledger.finish(request_id, status=status, usage=usage, result_hash=semantic_hash(response))
        return response
    finally:
        client.close()
