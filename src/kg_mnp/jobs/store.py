"""SQLite-backed jobs, idempotency keys and fencing leases."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from kg_mnp.contracts.canonical import semantic_hash

from .models import JobRecord


class JobStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, project_id TEXT,
                    request_digest TEXT NOT NULL, request_json TEXT NOT NULL,
                    status TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
                    fencing_token INTEGER NOT NULL DEFAULT 0, lease_owner TEXT,
                    lease_expires_at REAL, result_json TEXT, error_json TEXT,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    project_id TEXT NOT NULL, idem_key TEXT NOT NULL,
                    request_digest TEXT NOT NULL, job_id TEXT NOT NULL,
                    PRIMARY KEY(project_id, idem_key)
                );
                CREATE TABLE IF NOT EXISTS job_events (
                    job_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
                    observed_at REAL NOT NULL, PRIMARY KEY(job_id, sequence)
                );
                """
            )

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def request_digest(operation_id: str, project_id: str | None, parameters: dict[str, Any]) -> str:
        return semantic_hash({"operation_id": operation_id, "project_id": project_id, "parameters": parameters})

    def create(self, *, operation_id: str, project_id: str | None, parameters: dict[str, Any], idempotency_key: str | None = None) -> tuple[JobRecord, bool]:
        digest = self.request_digest(operation_id, project_id, parameters)
        now = time.time()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                existing = connection.execute("SELECT * FROM idempotency WHERE project_id IS ? AND idem_key = ?", (project_id, idempotency_key)).fetchone()
                if existing:
                    if existing["request_digest"] != digest:
                        raise ValueError("idempotency key was reused with a different request")
                    return self.get(existing["job_id"]), True
            job_id = "job_" + uuid4().hex
            connection.execute("INSERT INTO jobs(job_id,operation_id,project_id,request_digest,request_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (job_id, operation_id, project_id, digest, json.dumps(parameters, sort_keys=True), "QUEUED", now, now))
            if idempotency_key:
                connection.execute("INSERT INTO idempotency(project_id,idem_key,request_digest,job_id) VALUES(?,?,?,?)", (project_id, idempotency_key, digest, job_id))
            self._event(connection, job_id, "JOB_QUEUED", {})
            connection.commit()
        return self.get(job_id), False

    def _event(self, connection: sqlite3.Connection, job_id: str, event_type: str, payload: dict[str, Any]) -> None:
        sequence = connection.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM job_events WHERE job_id = ?", (job_id,)).fetchone()[0]
        connection.execute("INSERT INTO job_events(job_id,sequence,event_type,payload_json,observed_at) VALUES(?,?,?,?,?)", (job_id, sequence, event_type, json.dumps(payload, sort_keys=True), time.time()))

    def get(self, job_id: str) -> JobRecord:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        return JobRecord(row["job_id"], row["operation_id"], row["project_id"], row["request_digest"], row["status"], row["attempt"], row["fencing_token"], row["lease_owner"], row["lease_expires_at"], json.loads(row["result_json"]) if row["result_json"] else None, json.loads(row["error_json"]) if row["error_json"] else None)

    def claim(self, *, worker_id: str, lease_seconds: float = 30) -> JobRecord | None:
        now = time.time()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM jobs WHERE status = 'QUEUED' OR (status = 'RUNNING' AND lease_expires_at < ?) ORDER BY created_at LIMIT 1", (now,)).fetchone()
            if not row:
                connection.commit()
                return None
            token = int(row["fencing_token"]) + 1
            connection.execute("UPDATE jobs SET status='RUNNING', attempt=attempt+1, fencing_token=?, lease_owner=?, lease_expires_at=?, updated_at=? WHERE job_id=?", (token, worker_id, now + lease_seconds, now, row["job_id"]))
            self._event(connection, row["job_id"], "JOB_CLAIMED", {"worker_id": worker_id, "fencing_token": token})
            connection.commit()
        return self.get(row["job_id"])

    def parameters(self, job_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT request_json FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        return json.loads(row[0])

    def complete(self, job_id: str, *, worker_id: str, fencing_token: int, result: dict[str, Any]) -> JobRecord:
        return self._finish(job_id, worker_id, fencing_token, "SUCCEEDED", result=result)

    def fail(self, job_id: str, *, worker_id: str, fencing_token: int, error: dict[str, Any]) -> JobRecord:
        return self._finish(job_id, worker_id, fencing_token, "FAILED", error=error)

    def _finish(self, job_id: str, worker_id: str, fencing_token: int, status: str, *, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> JobRecord:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute("UPDATE jobs SET status=?, lease_owner=NULL, lease_expires_at=NULL, result_json=?, error_json=?, updated_at=? WHERE job_id=? AND status='RUNNING' AND lease_owner=? AND fencing_token=?", (status, json.dumps(result, sort_keys=True) if result is not None else None, json.dumps(error, sort_keys=True) if error is not None else None, time.time(), job_id, worker_id, fencing_token)).rowcount
            if changed != 1:
                connection.rollback()
                raise ValueError("stale job fencing token")
            self._event(connection, job_id, "JOB_" + status, result or error or {})
            connection.commit()
        return self.get(job_id)

    def events(self, job_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT sequence,event_type,payload_json,observed_at FROM job_events WHERE job_id=? ORDER BY sequence", (job_id,)).fetchall()
        return [{"sequence": row[0], "event_type": row[1], "payload": json.loads(row[2]), "observed_at": row[3]} for row in rows]
