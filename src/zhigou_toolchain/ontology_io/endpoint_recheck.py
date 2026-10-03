"""User-authorized, eight-case compatibility recheck. Not benchmark generation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

import httpx

from zhigou_toolchain.contracts.canonical import semantic_hash

from .cli import load, save
from .live_budget import BudgetLedger
from .live_runner import supervisor_lock

ENDPOINT = "http://localhost:51900/v1/"
MODELS = ("gpt-5.6-luna", "gpt-6-astra")
ROUTES = ("chat/completions", "responses")
CASES = ("normal_utf8_json", "output_limit_128")
PLAN_ID = "localhost51900-model-recheck-20260921-v1"


def payload(model, route, case):
    if model not in MODELS or route not in ROUTES or case not in CASES:
        raise ValueError("UNREGISTERED_RECHECK_CASE")
    normal = case == "normal_utf8_json"
    instruction = ('Return exactly this JSON object, with the Chinese text unchanged: {"ok":true,"label":"本体"}' if normal else
        'Return a JSON object with "numbers" containing every integer from 1 to 500 in order. Do not abbreviate.')
    if route == "chat/completions":
        return {"model": model, "messages": [{"role": "system", "content": "Synthetic API compatibility test. Return only JSON; no tools or hidden reasoning."},
            {"role": "user", "content": instruction}], "reasoning_effort": "low", "max_completion_tokens": 128,
            "response_format": {"type": "json_object"}, "stream": False, "store": False, "n": 1}
    return {"model": model, "instructions": "Synthetic API compatibility test. Return only JSON; no tools or hidden reasoning.",
        "input": [{"role": "user", "content": instruction}], "reasoning": {"effort": "low"}, "max_output_tokens": 128,
        "text": {"format": {"type": "json_object"}}, "stream": False, "store": False}


def public_fields(raw, route):
    """Normalize only public output/usage. No reasoning fields or raw headers."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        data = None
    envelope_kind = "JSON"
    if not isinstance(data, dict):
        envelope_kind = "SSE_OR_UNPARSEABLE"
        data = {}
        for line in raw.decode("utf-8", errors="replace").splitlines():
            if not line.startswith("data:"):
                continue
            try:
                item = json.loads(line[5:].strip())
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("type") in {"response.completed", "response.incomplete"} and isinstance(item.get("response"), dict):
                data = item["response"]
    counts, texts, finish = {}, [], None
    usage = data.get("usage") or {}
    usage = usage if isinstance(usage, dict) else {}
    if route == "chat/completions":
        fields = {"prompt_tokens": "input_tokens", "completion_tokens": "output_tokens", "total_tokens": "total_tokens"}
        choices = data.get("choices")
        if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict):
            choice = choices[0]
            finish = choice.get("finish_reason")
            message = choice.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                texts.append(message["content"])
    else:
        fields = {"input_tokens": "input_tokens", "output_tokens": "output_tokens", "total_tokens": "total_tokens"}
        finish = data.get("status")
        details = data.get("incomplete_details") or {}
        if finish == "incomplete" and isinstance(details, dict) and details.get("reason") == "max_output_tokens":
            finish = "length"
        for item in data.get("output", []) if isinstance(data.get("output"), list) else []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for part in item.get("content", []) if isinstance(item.get("content"), list) else []:
                if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    texts.append(part["text"])
    invalid = []
    for old, new in fields.items():
        if old in usage:
            if type(usage[old]) is int and usage[old] >= 0:
                counts[new] = usage[old]
            else:
                invalid.append(old)
    content = "".join(texts)
    # Store only the two intentionally synthetic output forms, not arbitrary
    # provider messages. The exact wire bytes remain hash-bound, not claimed full.
    try:
        decoded = json.loads(content)
    except ValueError:
        decoded = None
    allowed = (isinstance(decoded, dict) and set(decoded) == {"ok", "label"} and decoded["ok"] is True and decoded["label"] == "本体") or (isinstance(decoded, dict) and set(decoded) == {"numbers"}
        and isinstance(decoded["numbers"], list) and len(decoded["numbers"]) <= 1000 and all(type(i) is int for i in decoded["numbers"]))
    public = decoded if allowed else None
    return {"model": data.get("model") if data.get("model") in MODELS else None, "usage": counts, "invalid_usage_fields": invalid,
        "finish": finish if finish in {"stop", "length", "completed", "incomplete", "failed", "content_filter"} else None,
        "output_json": public, "output_sha256": hashlib.sha256(content.encode()).hexdigest() if content else None,
        "response_sha256": hashlib.sha256(raw).hexdigest(), "envelope_kind": envelope_kind,
        "capture": "PUBLIC_SYNTHETIC_WHITELIST_NOT_FULL_RESPONSE"}


def assess(public, model, case, http_status):
    counts = public["usage"]
    complete_usage = all(k in counts for k in ("input_tokens", "output_tokens", "total_tokens")) and counts.get("total_tokens") == counts.get("input_tokens", 0) + counts.get("output_tokens", 0)
    normal_ok = isinstance(public["output_json"], dict) and public["output_json"].get("ok") is True and public["output_json"].get("label") == "本体"
    reachable = http_status == 200 and public["model"] == model
    violation = counts.get("output_tokens", 0) > 128 or bool(public["invalid_usage_fields"])
    if violation:
        limit_status = "VIOLATED"
    elif complete_usage and public["finish"] == "length":
        limit_status = "TRUNCATION_OBSERVED_NOT_GLOBAL_PROOF"
    else:
        limit_status = "NOT_PROVEN"
    return {"model_responded": reachable, "normal_utf8_json_passed": reachable and normal_ok if case == "normal_utf8_json" else None,
        "requested_output_limit": 128, "output_limit_status": limit_status, "usage": counts,
        "budget_state": "USAGE_BOUND_VIOLATION" if violation else "SUCCEEDED" if reachable else "FAILED",
        "research_score": None, "full_resume": False}


def run(workspace, output, *, user_authorization):
    workspace, output = Path(workspace).resolve(), Path(output).resolve()
    if not user_authorization or output.exists() or not (workspace / "budget.sqlite").is_file():
        raise ValueError("EXPLICIT_AUTHORIZATION_AND_NEW_OUTPUT_REQUIRED")
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key or "\\" in key or not key.startswith("agt_codex_"):
        raise ValueError("LOCAL_CREDENTIAL_MISSING_OR_ESCAPED_USE_CONFIGURED_SECRET")
    with supervisor_lock(workspace):
        ledger = BudgetLedger(workspace / "budget.sqlite")
        before = ledger.snapshot()
        with ledger.connection() as conn:
            old_rows = [dict(r) for r in conn.execute("SELECT * FROM attempts ORDER BY request_id")]
            if conn.execute("SELECT name FROM sqlite_master WHERE name='endpoint_rechecks'").fetchone() and conn.execute(
                    "SELECT COUNT(*) FROM endpoint_rechecks WHERE plan_id=?", (PLAN_ID,)).fetchone()[0]:
                raise ValueError("EXPLICIT_RECHECK_PLAN_ALREADY_STARTED_DO_NOT_REPEAT")
        stop_hash = hashlib.sha256((workspace / "STOP").read_bytes()).hexdigest()
        output.mkdir(parents=True)
        plan = {"plan_id": PLAN_ID, "user_authorization": user_authorization, "endpoint": ENDPOINT,
            "models": MODELS, "routes": ROUTES, "cases": CASES, "max_cases": 8, "credential_recorded": False,
            "budget_before": before, "normal_vs_limit_checks_separate": True, "not_benchmark": True}
        save(output / "plan.json", plan)
        results = []
        with httpx.Client(base_url=ENDPOINT, headers={"Authorization": "Bearer " + key, "X-Agtools-Disable-Image-Generation": "true"},
                timeout=120, trust_env=False, follow_redirects=False) as client:
            models = client.get("models")
            models.raise_for_status()
            present = {r.get("id") for r in models.json().get("data", [])}
            save(output / "health.json", {"http_status": models.status_code, "requested_models_listed": [m for m in MODELS if m in present]})
            for model in MODELS:
                for route in ROUTES:
                    for case in CASES:
                        request = payload(model, route, case)
                        identity = {"model": model, "route": route, "case": case}
                        identifier = PLAN_ID + ":" + semantic_hash(identity)[:16]
                        case_dir = output / (model + "--" + route.replace("/", "-") + "--" + case)
                        case_dir.mkdir()
                        if model not in present:
                            result = {**identity, "status": "NOT_LISTED_NOT_CALLED"}
                            save(case_dir / "result.json", result)
                            results.append(result)
                            continue
                        authorization = {"plan_id": PLAN_ID, "user_authorization": user_authorization, "endpoint": ENDPOINT,
                            **identity, "request_sha256": semantic_hash(request), "max_cases": 8}
                        reserve = 128000 + len(json.dumps(request, ensure_ascii=False).encode()) + 2048
                        save(case_dir / "request.json", request)
                        ledger.reserve_endpoint_recheck(identifier, reserve, authorization=authorization)
                        started, http_status = perf_counter(), None
                        try:
                            response = client.post(route, json=request)
                            http_status = response.status_code
                            public = public_fields(response.content, route)
                        except httpx.HTTPError as exc:
                            public = public_fields(b"", route)
                            public["transport_error_type"] = type(exc).__name__
                        assessment = assess(public, model, case, http_status)
                        save(case_dir / "response-public.json", public)
                        result = {**identity, **assessment, "http_status": http_status, "duration_seconds": perf_counter() - started,
                            "request_id": identifier, "response_sha256": public["response_sha256"], "reserved_tokens": reserve}
                        try:
                            ledger.finish(identifier, status=result["budget_state"], usage=public["usage"].get("total_tokens"), result_hash=semantic_hash(public))
                        except ValueError as exc:
                            if str(exc) != "PROVIDER_EXCEEDED_RESERVED_TOKEN_BOUND":
                                raise
                        save(case_dir / "result.json", result)
                        results.append(result)
                        print(json.dumps({**identity, "http_status": http_status, "normal_json": result["normal_utf8_json_passed"],
                            "limit_status": result["output_limit_status"], "usage": result["usage"]}), flush=True)
        with ledger.connection() as conn:
            retained = [dict(r) for r in conn.execute("SELECT * FROM attempts WHERE request_id NOT LIKE ? ORDER BY request_id", (PLAN_ID + ":%",))]
        summary = {"status": "COMPATIBILITY_RECHECK_COMPLETE_NOT_BENCHMARK", "cases": results, "budget_before": before,
            "budget_after": ledger.snapshot(), "historical_attempts_unchanged": retained == old_rows,
            "stop_unchanged": hashlib.sha256((workspace / "STOP").read_bytes()).hexdigest() == stop_hash,
            "provider_attempts": "NOT_INDEPENDENTLY_OBSERVED", "full_e2e_complete": False, "quality_scores": None}
        save(output / "summary.json", summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--execute-authorized-recheck", action="store_true", required=True)
    args = parser.parse_args()
    result = run(args.workspace, args.output, user_authorization=load(args.authorization)["authorization_summary_without_credentials"])
    print(json.dumps({"status": result["status"], "budget": result["budget_after"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
