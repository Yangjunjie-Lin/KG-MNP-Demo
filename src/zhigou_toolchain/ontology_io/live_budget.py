"""Transactional, durable experiment budget shared by probes and every run.

Reserve BEFORE dispatch. Failed/uncertain attempts keep their reservation;
resume cannot refund them, erase them or reissue an identical request ID.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash


class BudgetLedger:
    def __init__(self, path):
        self.path = Path(path)

    def connection(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self, authorization):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if (not authorization.get("user_request") or type(authorization.get("max_calls")) is not int
                or type(authorization.get("max_reserved_tokens")) is not int
                or authorization["max_calls"] < 1 or authorization["max_reserved_tokens"] < 1):
            raise ValueError("INVALID_EXPLICIT_BUDGET_AUTHORIZATION")
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS authorization (id INTEGER PRIMARY KEY CHECK(id=1), digest TEXT NOT NULL, document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (request_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, reserved INTEGER NOT NULL,
                    state TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT, usage INTEGER, result_hash TEXT);
            """)
            row = conn.execute("SELECT digest FROM authorization WHERE id=1").fetchone()
            digest = semantic_hash(authorization)
            if row and row["digest"] != digest:
                raise ValueError("EXISTING_BUDGET_AUTHORIZATION_IMMUTABLE")
            if not row:
                conn.execute("INSERT INTO authorization VALUES (1, ?, ?)", (digest, json.dumps(authorization)))
            columns = {r[1] for r in conn.execute("PRAGMA table_info(attempts)")}
            if "reserved_at_dispatch" not in columns:
                conn.execute("ALTER TABLE attempts ADD COLUMN reserved_at_dispatch INTEGER")
            conn.execute("UPDATE attempts SET reserved_at_dispatch=reserved WHERE reserved_at_dispatch IS NULL")
            # A reported overrun must increase the charge, never undercount
            # known usage. The original pre-dispatch reservation stays intact.
            conn.execute("UPDATE attempts SET reserved=usage WHERE usage IS NOT NULL AND usage>reserved")

    def reserve(self, request_id, job_id, tokens):
        if type(tokens) is not int or tokens < 1:
            raise ValueError("INVALID_RESERVATION")
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            auth = json.loads(conn.execute("SELECT document FROM authorization WHERE id=1").fetchone()[0])
            if conn.execute("SELECT COUNT(*) FROM attempts WHERE state='USAGE_BOUND_VIOLATION'").fetchone()[0]:
                raise ValueError("GLOBAL_BUDGET_LATCHED_PROVIDER_LIMIT_NOT_ENFORCED")
            row = conn.execute("SELECT COUNT(*) AS calls, COALESCE(SUM(reserved),0) AS tokens FROM attempts").fetchone()
            if row["calls"] + 1 > auth["max_calls"] or row["tokens"] + tokens > auth["max_reserved_tokens"]:
                raise ValueError("GLOBAL_EXPERIMENT_BUDGET_EXHAUSTED")
            conn.execute("INSERT INTO attempts (request_id,job_id,reserved,reserved_at_dispatch,state,started_at) VALUES (?,?,?,?,'RESERVED',?)",
                (request_id, job_id, tokens, tokens, datetime.now(UTC).isoformat()))

    def finish(self, request_id, *, status, usage, result_hash):
        if status not in {"SUCCEEDED", "FAILED", "USAGE_BOUND_VIOLATION"}:
            raise ValueError("INVALID_BUDGET_ATTEMPT_STATUS")
        if usage is not None and (type(usage) is not int or usage < 0):
            raise ValueError("INVALID_PROVIDER_USAGE")
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM attempts WHERE request_id=?", (request_id,)).fetchone()
            if not row or row["state"] != "RESERVED":
                raise ValueError("BUDGET_ATTEMPT_ALREADY_FINAL_OR_MISSING")
            if usage is not None and usage > row["reserved"]:
                status = "USAGE_BOUND_VIOLATION"
            conn.execute("UPDATE attempts SET state=?, ended_at=?, usage=?, reserved=?, result_hash=? WHERE request_id=?",
                (status, datetime.now(UTC).isoformat(), usage, max(row["reserved"], usage or 0), result_hash, request_id))
        if status == "USAGE_BOUND_VIOLATION":
            raise ValueError("PROVIDER_EXCEEDED_RESERVED_TOKEN_BOUND")

    def snapshot(self):
        with self.connection() as conn:
            auth = json.loads(conn.execute("SELECT document FROM authorization WHERE id=1").fetchone()[0])
            row = dict(conn.execute("SELECT COUNT(*) AS calls, COALESCE(SUM(reserved),0) AS reserved_tokens, SUM(usage) AS known_tokens, "
                "COUNT(usage) AS known_usage_attempts FROM attempts").fetchone())
            states = {r[0]: r[1] for r in conn.execute("SELECT state,COUNT(*) FROM attempts GROUP BY state")}
        return {**row, "states": states, "max_calls": auth["max_calls"], "max_reserved_tokens": auth["max_reserved_tokens"],
            "remaining_calls": auth["max_calls"] - row["calls"], "remaining_reserved_tokens": auth["max_reserved_tokens"] - row["reserved_tokens"],
            "provider_limit_latched": bool(states.get("USAGE_BOUND_VIOLATION")),
            "known_tokens_are_partial": row["known_usage_attempts"] != row["calls"], "cost": None}
