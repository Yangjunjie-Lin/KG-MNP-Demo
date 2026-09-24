"""Explicitly authorized local usage monitoring, not provider-side token control.

The legacy ledger, reservations and violation states remain intact. Only a
new, explicitly bound policy may acknowledge historical violations for new
requests. Known successful usage settles a new reservation; failures/unknowns
retain it. A new violation or unknown usage stops the policy.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from zhigou_toolchain.contracts.canonical import semantic_hash

POLICY_KIND = "LOCAL_USAGE_MONITOR_V1_NOT_PROVIDER_HARD_CAP"
MODEL = "gpt-5.6-luna"
ENDPOINT = "http://localhost:51900/v1"
OUTPUT_RESERVATION = 128000


def protocol_monitor(protocol):
    document = protocol.total_run_authorization or {}
    ref = document.get("budget_monitor")
    if ref is None:
        return None
    if set(ref) != {"policy_id", "policy_sha256", "kind", "output_reservation_tokens"} or ref["kind"] != POLICY_KIND or ref["output_reservation_tokens"] != OUTPUT_RESERVATION:
        raise ValueError("INVALID_MONITOR_PROTOCOL_REFERENCE")
    return ref


def totals(conn):
    rows = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "monitored_attempts" not in rows:
        row = conn.execute("SELECT COUNT(*) AS calls, COALESCE(SUM(reserved),0) AS charged FROM attempts").fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS calls, COALESCE(SUM(COALESCE(m.charge,a.reserved)),0) AS charged "
            "FROM attempts a LEFT JOIN monitored_attempts m ON a.request_id=m.request_id").fetchone()
    return dict(row)


def authorize(ledger, document):
    expected = {"policy_id", "kind", "user_request", "context", "model_id", "endpoint_sha256", "reasoning_effort",
        "max_calls", "max_reserved_tokens", "acknowledged_violation_ids", "prior_attempts_sha256", "acknowledged_stop_sha256",
        "output_reservation_tokens", "settlement", "single_request_hard_cap_guaranteed"}
    if (set(document) not in (expected, expected | {"transport_recovery"}) or not document["user_request"] or not document["context"]
            or document["kind"] != POLICY_KIND or document["model_id"] != MODEL
            or document["endpoint_sha256"] != semantic_hash(ENDPOINT) or document["reasoning_effort"] != "low"
            or document["output_reservation_tokens"] != OUTPUT_RESERVATION
            or document["settlement"] != "KNOWN_SUCCESSES_ACTUAL_FAILURES_OR_UNKNOWNS_KEEP_RESERVATION"
            or document["single_request_hard_cap_guaranteed"] is not False
            or not document["policy_id"].isalnum()):
        raise ValueError("EXPLICIT_LOCAL_MONITOR_AUTHORIZATION_REQUIRED")
    if "transport_recovery" in document and document["transport_recovery"] != {"max_attempts": 3, "backoff_seconds": 5, "semantic_retry": False}:
        raise ValueError("INVALID_BOUNDED_TRANSPORT_RECOVERY")
    with ledger.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        auth = json.loads(conn.execute("SELECT document FROM authorization WHERE id=1").fetchone()[0])
        if any(document[k] != auth[k] for k in ("max_calls", "max_reserved_tokens")):
            raise ValueError("MONITOR_CANNOT_CHANGE_GLOBAL_LIMITS")
        prior = [dict(r) for r in conn.execute("SELECT * FROM attempts ORDER BY request_id")]
        violations = sorted(r["request_id"] for r in prior if r["state"] == "USAGE_BOUND_VIOLATION")
        if document["prior_attempts_sha256"] != semantic_hash(prior) or document["acknowledged_violation_ids"] != violations:
            raise ValueError("MONITOR_HISTORY_CHANGED")
        if any(r["state"] == "RESERVED" for r in prior):
            raise ValueError("MONITOR_CANNOT_ACKNOWLEDGE_UNKNOWN_INFLIGHT_REQUEST")
        conn.execute("""CREATE TABLE IF NOT EXISTS monitor_policies (
            policy_id TEXT PRIMARY KEY, digest TEXT NOT NULL, document TEXT NOT NULL, created_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS monitored_attempts (
            request_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL, charge INTEGER NOT NULL,
            advisory_exceeded INTEGER NOT NULL DEFAULT 0, halt_reason TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS transport_recovery_ack (
            request_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL, job_id TEXT NOT NULL,
            job_attempt INTEGER NOT NULL, response_sha256 TEXT NOT NULL, recorded_at TEXT NOT NULL)""")
        conn.execute("INSERT INTO monitor_policies VALUES (?,?,?,?)", (document["policy_id"], semantic_hash(document),
            json.dumps(document, ensure_ascii=False, sort_keys=True), datetime.now(UTC).isoformat()))
    return {"policy_id": document["policy_id"], "policy_sha256": semantic_hash(document), "kind": POLICY_KIND,
        "output_reservation_tokens": OUTPUT_RESERVATION}


def policy(conn, ref):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "monitor_policies" not in tables:
        raise ValueError("MONITOR_POLICY_NOT_AUTHORIZED")
    row = conn.execute("SELECT * FROM monitor_policies WHERE policy_id=?", (ref["policy_id"],)).fetchone()
    if not row or row["digest"] != ref["policy_sha256"]:
        raise ValueError("MONITOR_POLICY_NOT_AUTHORIZED")
    document = json.loads(row["document"])
    if semantic_hash(document) != row["digest"] or ref["kind"] != document["kind"] or ref["output_reservation_tokens"] != document["output_reservation_tokens"]:
        raise ValueError("MONITOR_POLICY_CHANGED")
    return document


def require_ready(conn, ref):
    document = policy(conn, ref)
    violations = {r[0] for r in conn.execute("SELECT request_id FROM attempts WHERE state='USAGE_BOUND_VIOLATION'")}
    if violations - set(document["acknowledged_violation_ids"]):
        raise ValueError("MONITOR_NEW_VIOLATION_LATCHED")
    has_ack = conn.execute("SELECT name FROM sqlite_master WHERE name='transport_recovery_ack'").fetchone()
    query = ("SELECT COUNT(*) FROM monitored_attempts m LEFT JOIN transport_recovery_ack r ON m.request_id=r.request_id AND m.policy_id=r.policy_id "
        "WHERE m.policy_id=? AND m.halt_reason IS NOT NULL AND r.request_id IS NULL" if has_ack else
        "SELECT COUNT(*) FROM monitored_attempts WHERE policy_id=? AND halt_reason IS NOT NULL")
    if conn.execute(query, (ref["policy_id"],)).fetchone()[0]:
        raise ValueError("MONITOR_NEW_FAILURE_OR_UNKNOWN_USAGE_LATCHED")
    return document


def transient_response(response):
    if response.get("ok") is not False:
        return False
    transport = response.get("transport") or {}
    return (transport.get("error_type") in {"ReadTimeout", "ConnectTimeout", "ConnectError", "ReadError", "RemoteProtocolError"}
        or transport.get("http_status") in {408, 500, 502, 503, 504}
        or response.get("error_code") == "TRANSPORT_WALLTIME_EXCEEDED")


def acknowledge_transport_retry(ledger, ref, job_id, job_attempt, responses):
    """Append an acknowledgement under the frozen retry policy; never refund.

    Only actual hash-bound failed transport responses can be acknowledged.
    Invalid model JSON, semantic failures, 401/403/429 and budget overruns are
    not eligible. The immutable failed request remains FAILED with its charge.
    """
    if type(job_attempt) is not int or job_attempt not in {1, 2} or not responses:
        raise ValueError("TRANSPORT_RETRY_LIMIT_OR_EVIDENCE_INVALID")
    with ledger.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        document = policy(conn, ref)
        if document.get("transport_recovery") != {"max_attempts": 3, "backoff_seconds": 5, "semantic_retry": False}:
            raise ValueError("TRANSPORT_RETRY_NOT_AUTHORIZED")
        for request_id, response in responses.items():
            prefix = f"{job_id}:attempt-{job_attempt:02d}:call-"
            if not request_id.startswith(prefix) or not request_id[len(prefix):].isdigit() or not transient_response(response):
                raise ValueError("ONLY_BOUND_TRANSIENT_REQUESTS_CAN_RETRY")
            row = conn.execute("SELECT a.*,m.policy_id FROM attempts a JOIN monitored_attempts m ON a.request_id=m.request_id WHERE a.request_id=?", (request_id,)).fetchone()
            if (not row or row["job_id"] != job_id or row["policy_id"] != ref["policy_id"] or row["state"] != "FAILED"
                    or row["result_hash"] != semantic_hash(response)):
                raise ValueError("TRANSPORT_RETRY_LEDGER_BINDING_CHANGED")
            conn.execute("INSERT INTO transport_recovery_ack VALUES (?,?,?,?,?,?)", (request_id, ref["policy_id"], job_id,
                job_attempt, semantic_hash(response), datetime.now(UTC).isoformat()))


def reserve(ledger, ref, request_id, job_id, tokens, *, model_id, endpoint_sha256, reasoning_effort):
    if type(tokens) is not int or not OUTPUT_RESERVATION < tokens <= OUTPUT_RESERVATION + 32768:
        raise ValueError("INVALID_MONITOR_RESERVATION")
    with ledger.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        document = require_ready(conn, ref)
        if (model_id, endpoint_sha256, reasoning_effort) != (document["model_id"], document["endpoint_sha256"], document["reasoning_effort"]):
            raise ValueError("MONITOR_MODEL_OR_ENDPOINT_CHANGED")
        current = totals(conn)
        if current["calls"] + 1 > document["max_calls"] or current["charged"] + tokens > document["max_reserved_tokens"]:
            raise ValueError("GLOBAL_EXPERIMENT_BUDGET_EXHAUSTED")
        conn.execute("INSERT INTO attempts (request_id,job_id,reserved,reserved_at_dispatch,state,started_at) VALUES (?,?,?,?,'RESERVED',?)",
            (request_id, job_id, tokens, tokens, datetime.now(UTC).isoformat()))
        conn.execute("INSERT INTO monitored_attempts (request_id,policy_id,charge) VALUES (?,?,?)", (request_id, ref["policy_id"], tokens))


def finish(ledger, ref, request_id, *, status, usage, result_hash, advisory_exceeded=False, halt_reason=None):
    if status not in {"SUCCEEDED", "FAILED", "USAGE_BOUND_VIOLATION"} or (usage is not None and (type(usage) is not int or usage < 0)):
        raise ValueError("INVALID_MONITORED_FINISH")
    with ledger.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        policy(conn, ref)
        row = conn.execute("SELECT a.*,m.policy_id FROM attempts a JOIN monitored_attempts m ON a.request_id=m.request_id WHERE a.request_id=?", (request_id,)).fetchone()
        if not row or row["state"] != "RESERVED" or row["policy_id"] != ref["policy_id"]:
            raise ValueError("MONITOR_ATTEMPT_FINAL_OR_UNBOUND")
        if usage is not None and usage > row["reserved"]:
            status, halt_reason = "USAGE_BOUND_VIOLATION", "DOCUMENTED_RESERVATION_EXCEEDED"
        if usage is None:
            halt_reason = halt_reason or "USAGE_UNKNOWN"
        charge = usage if status == "SUCCEEDED" and usage is not None and halt_reason is None else max(row["reserved"], usage or 0)
        conn.execute("UPDATE attempts SET state=?,ended_at=?,usage=?,reserved=?,result_hash=? WHERE request_id=?",
            (status, datetime.now(UTC).isoformat(), usage, max(row["reserved"], usage or 0), result_hash, request_id))
        conn.execute("UPDATE monitored_attempts SET charge=?,advisory_exceeded=?,halt_reason=? WHERE request_id=?",
            (charge, int(advisory_exceeded), halt_reason, request_id))
    if status == "USAGE_BOUND_VIOLATION" or halt_reason:
        raise ValueError("MONITORED_CALL_REQUIRES_STOP")


def snapshot(ledger, ref):
    with ledger.connection() as conn:
        document = policy(conn, ref)
        current = totals(conn)
        rows = conn.execute("SELECT COUNT(*) AS calls,COALESCE(SUM(advisory_exceeded),0) AS advisory_exceeded,"
            "SUM(CASE WHEN halt_reason IS NOT NULL THEN 1 ELSE 0 END) AS halted FROM monitored_attempts WHERE policy_id=?", (ref["policy_id"],)).fetchone()
        try:
            require_ready(conn, ref)
            ready = True
        except ValueError:
            ready = False
    return {"policy_id": ref["policy_id"], "ready": ready, "effective_charged_tokens": current["charged"],
        "remaining_monitored_tokens": document["max_reserved_tokens"] - current["charged"], "remaining_calls": document["max_calls"] - current["calls"],
        "new_policy_calls": rows["calls"], "advisory_limit_exceeded_calls": rows["advisory_exceeded"],
        "single_request_hard_cap_guaranteed": False, "settlement": document["settlement"]}
