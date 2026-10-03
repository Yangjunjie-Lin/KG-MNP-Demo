"""No network in these synthetic compatibility and budget tests."""
import json
import sqlite3

import pytest

from tests.upgrade.test_ontology_model_recovery import latched
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.ontology_io.endpoint_recheck import (
    CASES,
    ENDPOINT,
    MODELS,
    PLAN_ID,
    ROUTES,
    assess,
    payload,
    public_fields,
)


def auth(model="gpt-5.6-luna", route="responses", case="normal_utf8_json"):
    return {"plan_id": PLAN_ID, "user_authorization": "SYNTHETIC_EXPLICIT_MODEL_RECHECK", "endpoint": ENDPOINT,
        "model": model, "route": route, "case": case, "request_sha256": semantic_hash(payload(model, route, case)), "max_cases": 8}


def test_recheck_all_eight_cases_stay_in_existing_budget_and_latch(tmp_path):
    ledger = latched(tmp_path, max_calls=12, max_tokens=2000000)
    count = 0
    for model in MODELS:
        for route in ROUTES:
            for case in CASES:
                count += 1
                ledger.reserve_endpoint_recheck(str(count), 131000, authorization=auth(model, route, case))
                ledger.finish(str(count), status="SUCCEEDED", usage=300, result_hash="synthetic")
    assert ledger.snapshot()["calls"] == 9 and ledger.snapshot()["provider_limit_latched"]
    assert ledger.snapshot()["max_reserved_tokens"] == 2000000
    with pytest.raises(ValueError, match="EXHAUSTED"):
        ledger.reserve_endpoint_recheck("extra", 131000, authorization=auth())
    with pytest.raises(ValueError, match="LATCHED"):
        ledger.reserve("full", "e2e", 1)


def test_case_cannot_repeat_with_different_request_identifier(tmp_path):
    ledger = latched(tmp_path, max_tokens=1000000)
    ledger.reserve_endpoint_recheck("first", 131000, authorization=auth())
    with pytest.raises(sqlite3.IntegrityError):
        ledger.reserve_endpoint_recheck("again", 131000, authorization=auth())
    assert ledger.snapshot()["calls"] == 2


@pytest.mark.parametrize("field,value", [("model", "other"), ("endpoint", "https://other.example/v1/"),
    ("route", "tools"), ("case", "benchmark_gold"), ("max_cases", 100), ("plan_id", "other"), ("user_authorization", "")])
def test_plan_cannot_expand_or_redirect_credentials(tmp_path, field, value):
    ledger = latched(tmp_path)
    with pytest.raises(ValueError, match="AUTHORIZATION"):
        ledger.reserve_endpoint_recheck("x", 131000, authorization={**auth(), field: value})
    assert ledger.snapshot()["calls"] == 1


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("route", ROUTES)
def test_requests_use_correct_route_parameter_names_and_utf8(model, route):
    value = payload(model, route, "normal_utf8_json")
    assert value["model"] == model and value["stream"] is False and value["store"] is False
    assert "本体" in json.dumps(value, ensure_ascii=False)
    if route == "responses":
        assert value["max_output_tokens"] == 128 and value["reasoning"]["effort"] == "low"
        assert "max_completion_tokens" not in value and "messages" not in value
    else:
        assert value["max_completion_tokens"] == 128 and value["reasoning_effort"] == "low"
        assert "max_output_tokens" not in value


@pytest.mark.parametrize("route", ROUTES)
def test_public_usage_and_output_without_any_reasoning(route):
    common = {"model": "gpt-6-astra", "reasoning_content": "SECRET_REASONING", "headers": {"Authorization": "SECRET_KEY"}}
    if route == "responses":
        common.update(status="completed", output=[{"type": "reasoning", "encrypted_content": "SECRET_REASONING"},
            {"type": "message", "content": [{"type": "output_text", "text": '{"ok":true,"label":"本体"}'}]}],
            usage={"input_tokens": 30, "output_tokens": 200, "total_tokens": 230})
    else:
        common.update(choices=[{"finish_reason": "stop", "message": {"content": '{"ok":true,"label":"本体"}', "reasoning": "SECRET_REASONING"}}],
            usage={"prompt_tokens": 30, "completion_tokens": 200, "total_tokens": 230})
    public = public_fields(json.dumps(common).encode(), route)
    assert "SECRET" not in json.dumps(public)
    result = assess(public, "gpt-6-astra", "normal_utf8_json", 200)
    assert result["normal_utf8_json_passed"] and result["output_limit_status"] == "VIOLATED"
    assert result["usage"]["total_tokens"] == 230 and not result["full_resume"]


def test_sse_length_completion_is_not_successful_json_or_unlimited_qualification():
    data = {"type": "response.incomplete", "response": {"model": "gpt-5.6-luna", "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"}, "output": [], "usage": {"input_tokens": 20, "output_tokens": 128, "total_tokens": 148}}}
    public = public_fields(("data: " + json.dumps(data) + "\n\n").encode(), "responses")
    result = assess(public, "gpt-5.6-luna", "output_limit_128", 200)
    assert result["output_limit_status"] == "TRUNCATION_OBSERVED_NOT_GLOBAL_PROOF" and result["research_score"] is None


def test_missing_usage_not_zero_and_bad_boolean_not_valid_answer():
    data = {"model": "gpt-5.6-luna", "choices": [{"message": {"content": '{"ok":1,"label":"本体"}'}}]}
    public = public_fields(json.dumps(data).encode(), "chat/completions")
    result = assess(public, "gpt-5.6-luna", "normal_utf8_json", 200)
    assert public["usage"] == {} and result["output_limit_status"] == "NOT_PROVEN"
    assert not result["normal_utf8_json_passed"]
