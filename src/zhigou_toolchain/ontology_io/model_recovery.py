"""One budgeted, gold-free diagnostic for the explicitly requested Luna migration.

Never removes STOP, clears violations, creates a new budget or resumes a job.
An enforced-limit observation alone is not full experiment qualification.
"""
from __future__ import annotations

import argparse
import hashlib
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
from zhigou_toolchain.modeling.five_stage.tools import ModelLock

from .cli import load, save
from .contracts import Protocol
from .live_budget import BudgetLedger
from .live_runner import supervisor_lock

TARGET_MODEL = "gpt-5.6-luna"
OUTPUT_CEILING = 128000
MODEL_DOCUMENTATION = "https://developers.openai.com/api/docs/models/gpt-5.6-luna"


def probe_request():
    return {"instruction": "Synthetic output-limit diagnostic, not a benchmark. Return a JSON object with the integer array numbers containing every integer from 1 to 500, in order. Do not abbreviate or add commentary.",
        "content": {"first": 1, "last": 500}, "schema": {"type": "object", "additionalProperties": False,
            "properties": {"numbers": {"type": "array", "items": {"type": "integer"}, "minItems": 500, "maxItems": 500}},
            "required": ["numbers"]}, "allowed_iris": []}


def evaluate_probe(reply, *, requested_limit, reserved_tokens):
    """Inspect only public transport metadata, never provider private reasoning."""
    metadata = reply.get("receipt") or reply.get("public_response") or {}
    if reply.get("receipt"):
        public = metadata.get("response", {})
    else:
        public = metadata
    counts = metadata.get("usage") or {}
    required = ("prompt_tokens", "completion_tokens", "total_tokens")
    valid_usage = (all(type(counts.get(k)) is int and counts[k] >= 0 for k in required)
        and counts.get("prompt_tokens", 0) + counts.get("completion_tokens", 0) == counts.get("total_tokens")
        and not metadata.get("invalid_usage_fields"))
    usage = counts.get("total_tokens")
    usage = usage if type(usage) is int and usage >= 0 else None
    choices = public.get("choices") or []
    observed_model = public.get("model")
    finish = choices[0].get("finish_reason") if len(choices) == 1 and isinstance(choices[0], dict) else None
    if not valid_usage:
        status, budget_state = "INCONCLUSIVE_USAGE_UNAVAILABLE_OR_INVALID", "FAILED"
    elif counts["completion_tokens"] > requested_limit or counts["total_tokens"] > reserved_tokens:
        status, budget_state = "BLOCKED_PROVIDER_OUTPUT_LIMIT_NOT_ENFORCED", "USAGE_BOUND_VIOLATION"
    elif observed_model != TARGET_MODEL:
        status, budget_state = "BLOCKED_MODEL_ID_MISMATCH", "FAILED"
    elif finish == "length":
        status, budget_state = "LIMIT_TRUNCATION_OBSERVED_NOT_FULL_QUALIFICATION", "SUCCEEDED"
    else:
        status, budget_state = "INCONCLUSIVE_OUTPUT_DID_NOT_EXERCISE_LIMIT", "FAILED"
    return {"status": status, "budget_state": budget_state, "usage": usage, "observed_model": observed_model,
        "finish_reason": finish, "reported_usage": {k: counts[k] for k in required if type(counts.get(k)) is int and counts[k] >= 0},
        "requested_max_completion_tokens": requested_limit, "research_score": None, "full_resume_authorized_by_probe": False}


def probe(workspace, output, *, user_request):
    workspace, output = Path(workspace).resolve(), Path(output).resolve()
    if not isinstance(user_request, str) or not user_request.strip():
        raise ValueError("EXPLICIT_CURRENT_USER_REQUEST_REQUIRED")
    if not (workspace / "budget.sqlite").is_file():
        raise ValueError("EXISTING_BUDGET_LEDGER_REQUIRED")
    if output.exists() or output.is_relative_to(workspace / "revisions"):
        raise ValueError("NEW_INDEPENDENT_PROBE_OUTPUT_REQUIRED")
    with supervisor_lock(workspace):
        return _probe(workspace, output, user_request)


def _probe(workspace, output, user_request):
    ledger = BudgetLedger(workspace / "budget.sqlite")
    before = ledger.snapshot()
    if not before["provider_limit_latched"]:
        raise ValueError("RECOVERY_REQUIRES_PRIOR_LATCH")
    with ledger.connection() as conn:
        previous = [dict(r) for r in conn.execute("SELECT * FROM attempts ORDER BY request_id")]
    stop = workspace / "STOP"
    stop_digest = hashlib.sha256(stop.read_bytes()).hexdigest() if stop.is_file() else None
    old = configured_client()
    try:
        if not isinstance(old, CompatibleClient):
            raise TypeError("RECOVERY_REQUIRES_EXISTING_COMPATIBLE_ROUTE")
        client = CompatibleClient(ModelLock(TARGET_MODEL, "configured-alias:" + TARGET_MODEL, old.lock.location),
            api_key=os.environ.get("OPENAI_API_KEY"), reasoning_effort="low", timeout_seconds=120)
        endpoint_sha256 = semantic_hash(old.lock.location)
    finally:
        old.close()
    try:
        health = client.health()  # GET only; no paid fallback or alternate endpoint.
    finally:
        client.close()
    protocol = Protocol.model_validate({"protocol_id": "luna-output-limit-diagnostic-v1", "model_id": TARGET_MODEL,
        "declared_revision": "configured-alias:" + TARGET_MODEL, "reasoning_effort": "low",
        "systems": ["DirectGeneralLLM"], "replicates": 1, "request_profile": {"timeout_seconds": 120},
        "budget": {"max_calls": 1, "max_output_tokens": 128, "max_total_tokens": 32768}})
    request = probe_request()
    reservation = OUTPUT_CEILING + len(json.dumps(request, ensure_ascii=False).encode()) + 2048
    authorization = {"user_request": user_request, "model_id": TARGET_MODEL, "endpoint_sha256": endpoint_sha256,
        "request_sha256": semantic_hash(request), "max_calls": 1, "documented_output_ceiling": OUTPUT_CEILING,
        "purpose": "SYNTHETIC_LIMIT_DIAGNOSTIC_NOT_RESUME",
        "prior_violation_ids": sorted(r["request_id"] for r in previous if r["state"] == "USAGE_BOUND_VIOLATION")}
    request_id = "luna-recovery-probe:" + semantic_hash({"model": TARGET_MODEL, "endpoint": endpoint_sha256})[:24]
    output.mkdir(parents=True, exist_ok=False)
    save(output / "authorization.json", authorization)
    save(output / "request.json", request)
    save(output / "protocol.json", protocol.model_dump(mode="json"))
    save(output / "preflight.json", {"health": health, "budget": before, "request_id": request_id,
        "reserved_tokens": reservation, "model_documentation": MODEL_DOCUMENTATION,
        "output_ceiling_attestation": "OFFICIAL_MODEL_DOCUMENTATION_NOT_GATEWAY_BILLING_GUARANTEE",
        "old_attempts_sha256": semantic_hash(previous), "stop_sha256": stop_digest})
    ledger.reserve_recovery_probe(request_id, reservation, authorization=authorization)
    env = dict(os.environ)
    env.update(OPENAI_TEXT_MODEL=TARGET_MODEL, OPENAI_REASONING_EFFORT="low", PYTHONUTF8="1",
        ZHIGOU_LLM_REVISION="configured-alias:" + TARGET_MODEL, KG_MNP_LLM_REVISION="configured-alias:" + TARGET_MODEL)
    command = {"request": request, "protocol": protocol.model_dump(mode="json"), "endpoint_sha256": endpoint_sha256}
    try:
        process = subprocess.run([sys.executable, "-m", "zhigou_toolchain.ontology_io.transport_worker"],
            input=json.dumps(command, ensure_ascii=False).encode(), capture_output=True, timeout=150, env=env, check=False)
        reply = json.loads(process.stdout) if process.returncode == 0 else {"ok": False, "error_code": "TRANSPORT_PROCESS_FAILED"}
        if not isinstance(reply, dict):
            raise TypeError("INVALID_TRANSPORT_ENVELOPE")
    except subprocess.TimeoutExpired:
        reply = {"ok": False, "error_code": "TRANSPORT_WALLTIME_EXCEEDED"}
    except (ValueError, TypeError, OSError):
        reply = {"ok": False, "error_code": "TRANSPORT_PROCESS_RESPONSE_INVALID"}
    save(output / "response.json", reply)
    result = evaluate_probe(reply, requested_limit=128, reserved_tokens=reservation)
    try:
        ledger.finish(request_id, status=result["budget_state"], usage=result["usage"], result_hash=semantic_hash(reply))
    except ValueError as exc:
        if str(exc) != "PROVIDER_EXCEEDED_RESERVED_TOKEN_BOUND":
            raise
    with ledger.connection() as conn:
        retained = [dict(r) for r in conn.execute("SELECT * FROM attempts WHERE request_id!=? ORDER BY request_id", (request_id,))]
    if retained != previous or (hashlib.sha256(stop.read_bytes()).hexdigest() if stop.is_file() else None) != stop_digest:
        raise ValueError("RECOVERY_HISTORICAL_EVIDENCE_CHANGED")
    result.update(budget_before=before, budget_after=ledger.snapshot(), historical_attempts_unchanged=True,
        stop_unchanged=True, model_call_reservations_this_probe=1, global_budget_increased=False,
        source_kind="LIVE_SYNTHETIC_TRANSPORT_DIAGNOSTIC_NOT_BENCHMARK", request_id=request_id)
    save(output / "result.json", result)
    save(output / "sha256.json", {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file()})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True, help="JSON containing the current explicit user_request")
    parser.add_argument("--execute-authorized-probe", action="store_true", required=True)
    args = parser.parse_args()
    result = probe(args.workspace, args.output, user_request=load(args.authorization)["user_request"])
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
