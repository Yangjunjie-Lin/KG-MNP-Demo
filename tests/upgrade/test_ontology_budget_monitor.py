"""Synthetic budget-protocol transition tests. No real inference or credentials."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest

from tests.upgrade.test_ontology_model_recovery import latched
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.five_stage.compatible import CompatibleClient
from zhigou_toolchain.modeling.five_stage.tools import ModelLock
from zhigou_toolchain.ontology_io import budget_monitor
from zhigou_toolchain.ontology_io.formal_calls import task_protocol
from zhigou_toolchain.ontology_io.live_broker import dispatch


def policy_document(ledger, *, policy_id="testmonitor"):
    with ledger.connection() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM attempts ORDER BY request_id")]
    snap = ledger.snapshot()
    return {"policy_id": policy_id, "kind": budget_monitor.POLICY_KIND, "user_request": "SYNTHETIC_EXPLICIT_BUDGET_POLICY_CHANGE",
        "context": "Synthetic authorization, not actual user spend.", "model_id": budget_monitor.MODEL,
        "endpoint_sha256": semantic_hash(budget_monitor.ENDPOINT), "reasoning_effort": "low",
        "max_calls": snap["max_calls"], "max_reserved_tokens": snap["max_reserved_tokens"],
        "acknowledged_violation_ids": sorted(r["request_id"] for r in rows if r["state"] == "USAGE_BOUND_VIOLATION"),
        "prior_attempts_sha256": semantic_hash(rows), "acknowledged_stop_sha256": hashlib.sha256(b"OLD_STOP").hexdigest(),
        "output_reservation_tokens": 128000, "settlement": "KNOWN_SUCCESSES_ACTUAL_FAILURES_OR_UNKNOWNS_KEEP_RESERVATION",
        "single_request_hard_cap_guaranteed": False}


def reserve(ledger, ref, rid, tokens=131000):
    budget_monitor.reserve(ledger, ref, rid, "job", tokens, model_id=budget_monitor.MODEL,
        endpoint_sha256=semantic_hash(budget_monitor.ENDPOINT), reasoning_effort="low")


def test_transition_does_not_modify_old_rows_or_original_budget_latch(tmp_path):
    ledger = latched(tmp_path, max_calls=20, max_tokens=500000)
    before = ledger.snapshot()
    with ledger.connection() as conn:
        old_rows = [dict(r) for r in conn.execute("SELECT * FROM attempts")]
    ref = budget_monitor.authorize(ledger, policy_document(ledger))
    assert before == ledger.snapshot()
    assert budget_monitor.snapshot(ledger, ref)["ready"]
    with pytest.raises(ValueError, match="LATCHED"):
        ledger.reserve("legacy", "old-worker", 1)
    reserve(ledger, ref, "new")
    budget_monitor.finish(ledger, ref, "new", status="SUCCEEDED", usage=2000, result_hash="new", advisory_exceeded=True)
    state = budget_monitor.snapshot(ledger, ref)
    assert state["ready"] and state["effective_charged_tokens"] == 2110
    assert state["advisory_limit_exceeded_calls"] == 1 and ledger.snapshot()["provider_limit_latched"]
    assert ledger.snapshot()["reserved_tokens"] == 131110  # history keeps dispatched reservation
    with ledger.connection() as conn:
        assert dict(conn.execute("SELECT * FROM attempts WHERE request_id='old'").fetchone()) == old_rows[0]


@pytest.mark.parametrize("changed", ["max_calls", "max_reserved_tokens", "prior_attempts_sha256", "acknowledged_violation_ids", "model_id", "endpoint_sha256", "user_request"])
def test_expanded_or_unbound_policy_is_refused(tmp_path, changed):
    ledger = latched(tmp_path)
    document = policy_document(ledger)
    document[changed] = document[changed] + 1 if changed.startswith("max_") else [] if changed == "acknowledged_violation_ids" else ""
    with pytest.raises(ValueError):
        budget_monitor.authorize(ledger, document)
    assert ledger.snapshot()["calls"] == 1


def test_inflight_unknown_cannot_be_acknowledged_as_history(tmp_path):
    ledger = latched(tmp_path)
    # Insert a synthetic uncertain request, never alter the old failure.
    with ledger.connection() as conn:
        conn.execute("INSERT INTO attempts VALUES ('uncertain','job',100,'RESERVED','now',NULL,NULL,NULL,100)")
    with pytest.raises(ValueError, match="INFLIGHT"):
        budget_monitor.authorize(ledger, policy_document(ledger))


@pytest.mark.parametrize("status,usage,expected_charge,halts", [("SUCCEEDED", 1000, 1000, False), ("FAILED", 1000, 131000, False),
    ("FAILED", None, 131000, True), ("SUCCEEDED", None, 131000, True), ("SUCCEEDED", 140000, 140000, True)])
def test_settlement_unknown_and_overrun_behavior(tmp_path, status, usage, expected_charge, halts):
    ledger = latched(tmp_path, max_tokens=800000)
    ref = budget_monitor.authorize(ledger, policy_document(ledger))
    reserve(ledger, ref, "call")
    if halts:
        with pytest.raises(ValueError, match="STOP"):
            budget_monitor.finish(ledger, ref, "call", status=status, usage=usage, result_hash="response")
    else:
        budget_monitor.finish(ledger, ref, "call", status=status, usage=usage, result_hash="response")
    assert budget_monitor.snapshot(ledger, ref)["effective_charged_tokens"] == 110 + expected_charge
    assert budget_monitor.snapshot(ledger, ref)["ready"] is not halts
    if halts:
        with pytest.raises(ValueError, match="LATCHED"):
            reserve(ledger, ref, "later")


def test_total_admission_uses_existing_limit_and_atomic_reservations(tmp_path):
    ledger = latched(tmp_path, max_calls=10, max_tokens=270000)
    ref = budget_monitor.authorize(ledger, policy_document(ledger))
    reserve(ledger, ref, "a")
    reserve(ledger, ref, "b")
    with pytest.raises(ValueError, match="EXHAUSTED"):
        reserve(ledger, ref, "c")
    budget_monitor.finish(ledger, ref, "a", status="SUCCEEDED", usage=1000, result_hash="a")
    reserve(ledger, ref, "c")
    assert budget_monitor.snapshot(ledger, ref)["effective_charged_tokens"] == 263110


def test_unacknowledged_future_legacy_violation_stops_monitor(tmp_path):
    ledger = latched(tmp_path, max_tokens=500000)
    ref = budget_monitor.authorize(ledger, policy_document(ledger))
    with ledger.connection() as conn:
        conn.execute("INSERT INTO attempts VALUES ('future','legacy',1,'USAGE_BOUND_VIOLATION','now','now',1,'hash',1)")
    with pytest.raises(ValueError, match="NEW_VIOLATION"):
        reserve(ledger, ref, "new")


def test_model_or_reference_drift_cannot_bypass_monitor(tmp_path):
    ledger = latched(tmp_path)
    ref = budget_monitor.authorize(ledger, policy_document(ledger))
    with pytest.raises(ValueError, match="MODEL_OR_ENDPOINT"):
        budget_monitor.reserve(ledger, ref, "x", "job", 131000, model_id="gpt-6-astra", endpoint_sha256=semantic_hash(budget_monitor.ENDPOINT), reasoning_effort="low")
    with pytest.raises(ValueError, match="NOT_AUTHORIZED"):
        reserve(ledger, {**ref, "policy_sha256": "0" * 64}, "y")


@pytest.mark.parametrize("completion,usage_valid", [(9000, True), (9000, False), (129000, True)])
def test_actual_broker_advisory_overrun_differs_from_new_hard_reservation(tmp_path, monkeypatch, completion, usage_valid):
    ledger = latched(tmp_path, max_tokens=1000000)
    ref = budget_monitor.authorize(ledger, policy_document(ledger))
    protocol = task_protocol("llms4ol_2026--flagship", model_id=budget_monitor.MODEL,
        declared_revision="configured-alias:" + budget_monitor.MODEL, reasoning_effort="low").model_copy(update={"total_run_authorization": {"budget_monitor": ref}})
    client = CompatibleClient(ModelLock(protocol.model_id, protocol.declared_revision, budget_monitor.ENDPOINT), reasoning_effort="low", transport=httpx.MockTransport(lambda _: pytest.fail("no actual network")))
    monkeypatch.setattr("zhigou_toolchain.ontology_io.live_broker.configured_client", lambda: client)
    usage = {"prompt_tokens": 20, "completion_tokens": completion, "total_tokens": completion + 20} if usage_valid else {}
    reply = {"ok": True, "receipt": {"proposal": {}, "usage": usage}}
    monkeypatch.setattr("zhigou_toolchain.ontology_io.live_broker.subprocess.run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(reply).encode()))
    request = {"instruction": "SYNTHETIC", "content": {}, "schema": {"type": "object"}, "allowed_iris": []}
    options = {"protocol": protocol, "ledger": ledger, "job_id": "job", "request_id": "new", "directory": tmp_path / "call",
        "endpoint_sha256": semantic_hash(budget_monitor.ENDPOINT)}
    if completion > 128000 or not usage_valid:
        with pytest.raises(ValueError, match="STOP"):
            dispatch(request, **options)
    else:
        result = dispatch(request, **options)
        assert result["budget_monitor"]["advisory_limit_exceeded"]
        assert budget_monitor.snapshot(ledger, ref)["ready"]
    assert (tmp_path / "call/response.json").is_file()


def test_monitor_in_protocol_is_optional_and_not_an_authority_itself():
    p = task_protocol("llms4ol_2026--flagship", model_id="fixture", declared_revision="fixture", reasoning_effort=None)
    before = deepcopy(p.model_dump(mode="json"))
    assert budget_monitor.protocol_monitor(p) is None and p.model_dump(mode="json") == before
    with pytest.raises(ValueError):
        budget_monitor.protocol_monitor(p.model_copy(update={"total_run_authorization": {"budget_monitor": {"kind": "fake"}}}))
