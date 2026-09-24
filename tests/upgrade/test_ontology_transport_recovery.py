"""Bounded infrastructure recovery keeps original failures and all spending."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tests.upgrade.test_ontology_budget_monitor import policy_document
from tests.upgrade.test_ontology_model_recovery import latched
from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.ontology_io import budget_monitor, live_runner
from zhigou_toolchain.ontology_io.cli import save
from zhigou_toolchain.ontology_io.formal_calls import task_protocol
from zhigou_toolchain.ontology_io.live_inventory import call_response_path
from zhigou_toolchain.ontology_io.os_sandbox import command


def authorized(tmp_path, *, recovery=True):
    ledger = latched(tmp_path, max_calls=20, max_tokens=2000000)
    document = policy_document(ledger)
    if recovery:
        document["transport_recovery"] = {"max_attempts": 3, "backoff_seconds": 5, "semantic_retry": False}
    return ledger, budget_monitor.authorize(ledger, document)


def failed_call(ledger, ref, *, job="job", attempt=1, response=None):
    response = response or {"ok": False, "transport": {"error_type": "ReadTimeout", "http_status": None}, "public_response": None}
    rid = f"{job}:attempt-{attempt:02d}:call-1"
    budget_monitor.reserve(ledger, ref, rid, job, 131000, model_id=budget_monitor.MODEL,
        endpoint_sha256=semantic_hash(budget_monitor.ENDPOINT), reasoning_effort="low")
    with pytest.raises(ValueError, match="STOP"):
        budget_monitor.finish(ledger, ref, rid, status="FAILED", usage=None, result_hash=semantic_hash(response), halt_reason="PROVIDER_USAGE_INCOMPLETE_OR_INCONSISTENT")
    return rid, response


@pytest.mark.parametrize("transport", [{"error_type": "ReadTimeout", "http_status": None}, {"error_type": "HTTPStatusError", "http_status": 408}])
def test_ack_does_not_refund_or_rewrite_unknown_failure(tmp_path, transport):
    ledger, ref = authorized(tmp_path)
    rid, response = failed_call(ledger, ref, response={"ok": False, "transport": transport, "public_response": None})
    before = ledger.snapshot()
    with ledger.connection() as conn:
        old = dict(conn.execute("SELECT * FROM attempts WHERE request_id=?", (rid,)).fetchone())
    assert not budget_monitor.snapshot(ledger, ref)["ready"]
    budget_monitor.acknowledge_transport_retry(ledger, ref, "job", 1, {rid: response})
    assert budget_monitor.snapshot(ledger, ref)["ready"] and ledger.snapshot() == before
    with ledger.connection() as conn:
        assert dict(conn.execute("SELECT * FROM attempts WHERE request_id=?", (rid,)).fetchone()) == old
    assert budget_monitor.snapshot(ledger, ref)["effective_charged_tokens"] == 131110


def test_legacy_policy_cannot_recover_and_third_attempt_cannot_repeat(tmp_path):
    ledger, ref = authorized(tmp_path, recovery=False)
    rid, response = failed_call(ledger, ref)
    with pytest.raises(ValueError, match="NOT_AUTHORIZED"):
        budget_monitor.acknowledge_transport_retry(ledger, ref, "job", 1, {rid: response})
    with pytest.raises(ValueError, match="LIMIT"):
        budget_monitor.acknowledge_transport_retry(ledger, ref, "job", 3, {rid: response})


@pytest.mark.parametrize("response", [{"ok": False, "error_code": "MODEL_OUTPUT_REJECTED_SCHEMA"},
    {"ok": False, "transport": {"http_status": 401}}, {"ok": False, "transport": {"http_status": 403}},
    {"ok": False, "transport": {"http_status": 429}}, {"ok": True, "transport": {"error_type": "ReadTimeout"}}])
def test_semantics_authentication_and_quota_are_not_transient_retries(response):
    assert not budget_monitor.transient_response(response)


@pytest.mark.parametrize("mutation", ["hash", "job", "attempt"])
def test_retry_evidence_cannot_be_rebound(tmp_path, mutation):
    ledger, ref = authorized(tmp_path)
    rid, response = failed_call(ledger, ref)
    if mutation == "hash":
        response = {**response, "changed": True}
    with pytest.raises(ValueError):
        budget_monitor.acknowledge_transport_retry(ledger, ref, "other" if mutation == "job" else "job",
            2 if mutation == "attempt" else 1, {rid: response})


def test_new_budget_violation_cannot_be_acknowledged_as_timeout(tmp_path):
    ledger, ref = authorized(tmp_path)
    rid, response = failed_call(ledger, ref)
    with ledger.connection() as conn:
        conn.execute("UPDATE attempts SET state='USAGE_BOUND_VIOLATION' WHERE request_id=?", (rid,))
    with pytest.raises(ValueError, match="BINDING"):
        budget_monitor.acknowledge_transport_retry(ledger, ref, "job", 1, {rid: response})


def test_os_job_timeout_remains_explicitly_bounded(tmp_path):
    args = command(tmp_path, tmp_path, tmp_path, tmp_path, wall_timeout=1830)
    assert "1830s" in args and "--unshare-all" in args
    with pytest.raises(ValueError, match="BOUND"):
        command(tmp_path, tmp_path, tmp_path, tmp_path, wall_timeout=100000)


def test_attempt_responses_resolve_without_ambiguous_ids_or_path_escape(tmp_path):
    assert call_response_path(tmp_path, "job", "job:attempt-02:call-1") == tmp_path / "runs/job/attempt-02/calls/1/response.json"
    assert call_response_path(tmp_path, "job", "job:call-1") == tmp_path / "runs/job/calls/1/response.json"
    for value in ("other:call-1", "job:attempt-99:call-1", "job:attempt-../:call-1", "job:call-../secret"):
        with pytest.raises(ValueError):
            call_response_path(tmp_path, "job", value)


@pytest.mark.parametrize("transport", [{"error_type": "ReadTimeout", "http_status": None}, {"error_type": "HTTPStatusError", "http_status": 408}])
def test_runner_retries_transport_with_new_ids_and_retains_both_attempts(tmp_path, monkeypatch, transport):
    ledger, ref = authorized(tmp_path)
    task = "llms4ol_2026--flagship"
    rev = tmp_path / "revisions/r3"
    p = task_protocol(task, model_id=budget_monitor.MODEL, declared_revision="configured-alias:" + budget_monitor.MODEL,
        reasoning_effort="low").model_copy(update={"total_run_authorization": {"budget_monitor": ref}})
    save(rev / "manifest.json", {"budget_monitor": ref, "transport_recovery": {"max_attempts": 3, "backoff_seconds": 5, "semantic_retry": False},
        "isolation": {"passed": True}, "launcher_sha256": {}, "binding": {"endpoint_sha256": semantic_hash(budget_monitor.ENDPOINT)}})
    save(rev / "code-lock.json", {"files": {}})
    save(rev / "protocols" / (task + ".json"), p.model_dump(mode="json"))
    with live_runner.connect(tmp_path) as conn:
        conn.executescript("""CREATE TABLE jobs (job_id TEXT PRIMARY KEY,revision TEXT,phase TEXT,task TEXT,sample TEXT,system TEXT,replicate INTEGER,
            max_calls INTEGER,state TEXT,order_key TEXT,started TEXT,ended TEXT,result_path TEXT,result_hash TEXT,error TEXT);
            CREATE TABLE inputs (revision TEXT,phase TEXT,task TEXT,sample TEXT,payload TEXT);
            CREATE TABLE execution_attempts (job_id TEXT,attempt INTEGER,snapshot TEXT,PRIMARY KEY(job_id,attempt));""")
        conn.execute("INSERT INTO inputs VALUES ('r3','smoke',?,'sample',?)", (task, json.dumps({"sample_id": "sample"})))
        conn.execute("INSERT INTO jobs VALUES ('job','r3','smoke',?,'sample','DirectGeneralLLM',0,1,'PENDING','first',NULL,NULL,NULL,NULL,NULL)", (task,))
    calls = []

    def fake_job(job, **options):
        attempt = options["attempt"]
        calls.append(attempt)
        directory = options["directory"]
        if attempt == 1:
            rid, response = failed_call(ledger, ref, response={"ok": False, "transport": transport, "public_response": None})
            save(directory / "calls/1/response.json", response)
            raise ValueError("MONITORED_CALL_REQUIRES_STOP")
        rid = "job:attempt-02:call-1"
        budget_monitor.reserve(ledger, ref, rid, "job", 131000, model_id=budget_monitor.MODEL,
            endpoint_sha256=semantic_hash(budget_monitor.ENDPOINT), reasoning_effort="low")
        response = {"ok": True, "receipt": {"usage": {"total_tokens": 1000}}}
        budget_monitor.finish(ledger, ref, rid, status="SUCCEEDED", usage=1000, result_hash=semantic_hash(response))
        save(directory / "calls/1/response.json", response)
        result_path = directory / "output/result/result.json"
        save(result_path, {"status": "GENERATED", "prediction": {"triples": []}})
        return {"result_path": str(result_path)}

    monkeypatch.setattr(live_runner, "run_job", fake_job)
    monkeypatch.setattr(live_runner.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(live_runner.shutil, "disk_usage", lambda path: SimpleNamespace(free=10 * 1024 ** 3))
    result = live_runner.execute(tmp_path, "r3", "smoke")
    assert calls == [1, 2] and result["jobs"] == [{"phase": "smoke", "state": "GENERATED", "count": 1}]
    with live_runner.connect(tmp_path) as conn:
        history = [json.loads(r[0]) for r in conn.execute("SELECT snapshot FROM execution_attempts ORDER BY attempt")]
    assert [r["state"] for r in history] == ["FAILED", "GENERATED"]
    assert all(r["started"] is not None for r in history)
    assert (rev / "runs/job/attempt-01/calls/1/response.json").exists()
    assert (rev / "runs/job/attempt-02/calls/1/response.json").exists()
    assert ledger.snapshot()["calls"] == 3
    assert budget_monitor.snapshot(ledger, ref)["effective_charged_tokens"] == 132110
