"""Synthetic recovery-policy checks. Never contact a model or unlock generation."""
from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import pytest

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
from zhigou_toolchain.modeling.five_stage.tools import ModelLock
from zhigou_toolchain.ontology_io import model_recovery
from zhigou_toolchain.ontology_io.live_budget import BudgetLedger


def latched(tmp_path, *, max_calls=3, max_tokens=300000):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    ledger.initialize({"user_request": "SYNTHETIC_TEST_AUTHORIZATION", "max_calls": max_calls, "max_reserved_tokens": max_tokens})
    ledger.reserve("old", "spark-fixture", 100)
    with pytest.raises(ValueError, match="EXCEEDED"):
        ledger.finish("old", status="USAGE_BOUND_VIOLATION", usage=110, result_hash="old-response")
    return ledger


def authorization():
    return {"user_request": "SYNTHETIC_EXPLICIT_LUNA_RECOVERY", "model_id": "gpt-5.6-luna", "endpoint_sha256": "a" * 64,
        "request_sha256": semantic_hash(model_recovery.probe_request()), "prior_violation_ids": ["old"], "max_calls": 1,
        "documented_output_ceiling": 128000, "purpose": "SYNTHETIC_LIMIT_DIAGNOSTIC_NOT_RESUME"}


def test_recovery_probe_preserves_historical_latch_and_same_budget(tmp_path):
    ledger = latched(tmp_path)
    before = ledger.snapshot()
    ledger.reserve_recovery_probe("luna", 131000, authorization=authorization())
    ledger.finish("luna", status="SUCCEEDED", usage=140, result_hash="new-response")
    after = ledger.snapshot()
    assert after["calls"] == before["calls"] + 1
    assert after["max_calls"] == before["max_calls"] and after["max_reserved_tokens"] == before["max_reserved_tokens"]
    assert after["provider_limit_latched"] and after["states"]["USAGE_BOUND_VIOLATION"] == 1
    with pytest.raises(ValueError, match="LATCHED"):
        ledger.reserve("generation", "full", 1)
    with ledger.connection() as conn:
        row = dict(conn.execute("SELECT * FROM attempts WHERE request_id='old'").fetchone())
    assert row["result_hash"] == "old-response" and row["usage"] == 110 and row["reserved_at_dispatch"] == 100


@pytest.mark.parametrize("field,value", [("user_request", ""), ("model_id", "another-model"), ("max_calls", 2),
    ("max_calls", True), ("documented_output_ceiling", 8192), ("endpoint_sha256", "https://secret"),
    ("request_sha256", None), ("purpose", "RESUME_FULL")])
def test_recovery_refuses_expanded_or_unbound_authorization(tmp_path, field, value):
    ledger = latched(tmp_path)
    with pytest.raises(ValueError, match="AUTHORIZATION"):
        ledger.reserve_recovery_probe("luna", 131000, authorization={**authorization(), field: value})
    assert ledger.snapshot()["calls"] == 1


@pytest.mark.parametrize("calls,tokens", [(1, 300000), (3, 131000)])
def test_recovery_never_increases_global_limits(tmp_path, calls, tokens):
    ledger = latched(tmp_path, max_calls=calls, max_tokens=tokens)
    with pytest.raises(ValueError, match="EXHAUSTED"):
        ledger.reserve_recovery_probe("luna", 131000, authorization=authorization())
    assert ledger.snapshot()["calls"] == 1


def test_recovery_reservation_is_one_per_route_even_across_threads(tmp_path):
    ledger = latched(tmp_path, max_calls=20, max_tokens=3000000)

    def reserve(index):
        try:
            ledger.reserve_recovery_probe(f"probe-{index}", 131000, authorization=authorization())
            return True
        except sqlite3.IntegrityError:
            return False

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(reserve, range(10)))
    assert sum(results) == 1 and ledger.snapshot()["calls"] == 2


def reply(*, completion=128, finish="length", model="gpt-5.6-luna"):
    return {"ok": False, "public_response": {"model": model, "id": "synthetic",
        "usage": {"prompt_tokens": 50, "completion_tokens": completion, "total_tokens": completion + 50},
        "choices": [{"finish_reason": finish, "content": "{\"numbers\":[1,2"}]}}


@pytest.mark.parametrize("completion,finish,model,status", [
    (128, "length", "gpt-5.6-luna", "LIMIT_TRUNCATION_OBSERVED_NOT_FULL_QUALIFICATION"),
    (600, "stop", "gpt-5.6-luna", "BLOCKED_PROVIDER_OUTPUT_LIMIT_NOT_ENFORCED"),
    (50, "stop", "gpt-5.6-luna", "INCONCLUSIVE_OUTPUT_DID_NOT_EXERCISE_LIMIT"),
    (128, "length", "unexpected", "BLOCKED_MODEL_ID_MISMATCH")])
def test_probe_does_not_confuse_json_validity_with_output_limit(completion, finish, model, status):
    result = model_recovery.evaluate_probe(reply(completion=completion, finish=finish, model=model), requested_limit=128, reserved_tokens=131000)
    assert result["status"] == status and result["full_resume_authorized_by_probe"] is False
    assert result["research_score"] is None


@pytest.mark.parametrize("usage", [{}, {"total_tokens": 0}, {"prompt_tokens": 1, "completion_tokens": -1, "total_tokens": 0},
    {"prompt_tokens": 1, "completion_tokens": 128, "total_tokens": 1}])
def test_probe_missing_or_bad_usage_never_qualifies(usage):
    value = reply()
    value["public_response"]["usage"] = usage
    result = model_recovery.evaluate_probe(value, requested_limit=128, reserved_tokens=131000)
    assert result["status"] == "INCONCLUSIVE_USAGE_UNAVAILABLE_OR_INVALID"


def test_probe_charges_same_ledger_keeps_stop_no_gold_and_no_global_model_change(tmp_path, monkeypatch):
    ledger = latched(tmp_path)
    (tmp_path / "STOP").write_text("preserve-old-stop", encoding="utf-8")
    observed = []

    def health_handler(request):
        observed.append((request.method, request.url.path))
        return httpx.Response(200, json={"data": [{"id": "gpt-5.6-luna"}]})

    class TestClient(CompatibleClient):
        def __init__(self, lock, **kwargs):
            super().__init__(lock, transport=httpx.MockTransport(health_handler), **kwargs)

    monkeypatch.setattr(model_recovery, "CompatibleClient", TestClient)
    monkeypatch.setattr(model_recovery, "configured_client", lambda: TestClient(ModelLock("old-spark", "old", "http://localhost:1/v1")))
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "old-spark")
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC_SECRET_DO_NOT_EXPORT")
    attempts = []

    def run(*args, **kwargs):
        attempts.append(json.loads(kwargs["input"]))
        assert ledger.snapshot()["calls"] == 2  # reservation occurs before dispatch
        assert kwargs["env"]["OPENAI_TEXT_MODEL"] == "gpt-5.6-luna"
        return SimpleNamespace(returncode=0, stdout=json.dumps(reply(completion=600, finish="stop")).encode())

    monkeypatch.setattr(model_recovery.subprocess, "run", run)
    result = model_recovery.probe(tmp_path, tmp_path / "probe", user_request="SYNTHETIC_EXPLICIT_USER_RECOVERY")
    assert result["status"] == "BLOCKED_PROVIDER_OUTPUT_LIMIT_NOT_ENFORCED"
    assert result["historical_attempts_unchanged"] and result["stop_unchanged"]
    assert ledger.snapshot()["states"] == {"USAGE_BOUND_VIOLATION": 2}
    assert len(attempts) == 1 and attempts[0]["request"] == model_recovery.probe_request()
    assert observed == [("GET", "/v1/models")]
    import os
    assert os.environ["OPENAI_TEXT_MODEL"] == "old-spark"
    assert "SYNTHETIC_SECRET_DO_NOT_EXPORT" not in "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "probe").glob("*.json"))
    with pytest.raises(ValueError, match="NEW_INDEPENDENT"):
        model_recovery.probe(tmp_path, tmp_path / "probe", user_request="SYNTHETIC")
    assert len(attempts) == 1
