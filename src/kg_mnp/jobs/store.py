"""SQLite-backed jobs, idempotency keys and fencing leases."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
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
                CREATE TABLE IF NOT EXISTS idempotency_v2 (
                    principal_id TEXT NOT NULL, project_id TEXT NOT NULL,
                    operation_id TEXT NOT NULL, idem_key TEXT NOT NULL,
                    request_digest TEXT NOT NULL, job_id TEXT NOT NULL,
                    PRIMARY KEY(principal_id, project_id, operation_id, idem_key)
                );
                """
            )

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def request_digest(operation_id: str, project_id: str | None, parameters: dict[str, Any]) -> str:
        return semantic_hash({"operation_id": operation_id, "project_id": project_id, "parameters": parameters})

    def create(self, *, operation_id: str, project_id: str | None, parameters: dict[str, Any], idempotency_key: str | None = None, principal_id: str | None = None) -> tuple[JobRecord, bool]:
        principal_id = principal_id or parameters.get("__principal", {}).get("principal_id", "local-unattributed")
        digest = self.request_digest(operation_id, project_id, {key: value for key, value in parameters.items() if key != "__principal"})
        scope = (principal_id, project_id or "", operation_id, idempotency_key)
        now = time.time()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                existing = connection.execute("SELECT * FROM idempotency_v2 WHERE principal_id=? AND project_id=? AND operation_id=? AND idem_key=?", scope).fetchone()
                if existing:
                    if existing["request_digest"] != digest:
                        raise ValueError("idempotency key was reused with a different request")
                    connection.commit()
                    return self.get(existing["job_id"]), True
                legacy = connection.execute("SELECT 1 FROM idempotency WHERE project_id IS ? AND idem_key=?", (project_id, idempotency_key)).fetchone()
                if legacy:
                    raise ValueError("legacy idempotency entry requires administrator reconciliation")
            job_id = "job_" + uuid4().hex
            connection.execute("INSERT INTO jobs(job_id,operation_id,project_id,request_digest,request_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (job_id, operation_id, project_id, digest, json.dumps(parameters, sort_keys=True), "QUEUED", now, now))
            if idempotency_key:
                connection.execute("INSERT INTO idempotency_v2 VALUES(?,?,?,?,?,?)", (*scope, digest, job_id))
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
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now = time.time()
            expired = connection.execute("SELECT job_id FROM jobs WHERE status IN ('RUNNING','CANCEL_REQUESTED') AND lease_expires_at < ?", (now,)).fetchall()
            for item in expired:
                connection.execute("UPDATE jobs SET status='RECOVERY_REQUIRED',lease_owner=NULL,lease_expires_at=NULL,updated_at=? WHERE job_id=?", (now, item[0]))
                self._event(connection, item[0], "JOB_RECOVERY_REQUIRED", {})
            row = connection.execute("SELECT * FROM jobs WHERE status = 'QUEUED' ORDER BY created_at LIMIT 1").fetchone()
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

    def list_project(self, project_id: str, limit: int = 100):
        with self._connection() as conn:
            rows = conn.execute("SELECT job_id FROM jobs WHERE project_id=? ORDER BY created_at DESC LIMIT ?", (project_id, limit)).fetchall()
        return [self.get(row[0]) for row in rows]

    def complete(self, job_id: str, *, worker_id: str, fencing_token: int, result: dict[str, Any]) -> JobRecord:
        return self._finish(job_id, worker_id, fencing_token, "SUCCEEDED", result=result)

    def fail(self, job_id: str, *, worker_id: str, fencing_token: int, error: dict[str, Any]) -> JobRecord:
        return self._finish(job_id, worker_id, fencing_token, "FAILED", error=error)

    def _finish(self, job_id: str, worker_id: str, fencing_token: int, status: str, *, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> JobRecord:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now = time.time()
            changed = connection.execute("UPDATE jobs SET status=?, lease_owner=NULL, lease_expires_at=NULL, result_json=?, error_json=?, updated_at=? WHERE job_id=? AND status IN ('RUNNING','CANCEL_REQUESTED') AND lease_owner=? AND fencing_token=? AND lease_expires_at>?", (status, json.dumps(result, sort_keys=True) if result is not None else None, json.dumps(error, sort_keys=True) if error is not None else None, now, job_id, worker_id, fencing_token, now)).rowcount
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

    def renew(self, job_id: str, *, worker_id: str, fencing_token: int, lease_seconds: float = 30) -> None:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            # Lock wait time is not lease time: never revive an expired lease
            # with a timestamp captured before another writer released SQLite.
            now = time.time()
            changed = conn.execute("UPDATE jobs SET lease_expires_at=? WHERE job_id=? AND status='RUNNING' AND lease_owner=? AND fencing_token=? AND lease_expires_at>?",
                                   (now + lease_seconds, job_id, worker_id, fencing_token, now)).rowcount
            if changed != 1:
                raise ValueError("stale or cancelled job lease")
            conn.commit()

    def require_lease(self, job) -> None:
        current = self.get(job.job_id)
        if (current.status != "RUNNING" or current.lease_owner != job.lease_owner
                or current.fencing_token != job.fencing_token or (current.lease_expires_at or 0) <= time.time()):
            raise ValueError("stale or cancelled job lease")

    @contextmanager
    def commit_lease(self, job):
        """Serialize the *authority publication* with claim, cancel and renewal.

        The caller must keep its atomic authority switch inside this context.
        Computation must happen outside it, so cancellation/revocation can win.
        """
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job.job_id,)).fetchone()
            if (not row or row["status"] != "RUNNING" or row["lease_owner"] != job.lease_owner
                    or row["fencing_token"] != job.fencing_token or row["lease_expires_at"] <= time.time()):
                raise ValueError("stale or cancelled job lease")
            yield
            connection.commit()

    def recover_committed(self, job_id: str, result: dict[str, Any]) -> JobRecord:
        """Trusted application recovery after verifying an atomic core receipt."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            if row[0] != "SUCCEEDED":
                connection.execute("UPDATE jobs SET status='SUCCEEDED',lease_owner=NULL,lease_expires_at=NULL,"
                                   "result_json=?,error_json=NULL,updated_at=? WHERE job_id=?",
                                   (json.dumps(result, sort_keys=True), time.time(), job_id))
                self._event(connection, job_id, "JOB_COMMIT_RECOVERED", {})
            connection.commit()
        return self.get(job_id)

    def requeue_local(self, job_id: str, *, expected_attempt: int, requested_by: str) -> JobRecord:
        """Explicit recovery of an uncommitted, abandoned local attempt."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            if row["attempt"] != expected_attempt:
                raise ValueError("job attempt changed")
            if row["status"] == "QUEUED":
                return self.get(job_id)
            if row["status"] not in {"RUNNING", "RECOVERY_REQUIRED"} or (row["lease_expires_at"] or 0) > time.time():
                raise ValueError("job is not an abandoned local attempt")
            if connection.execute("SELECT 1 FROM job_events WHERE job_id=? AND event_type IN ('JOB_CANCEL_REQUESTED','JOB_CANCELLED')", (job_id,)).fetchone():
                raise ValueError("cancelled intent requires a new explicit request")
            connection.execute("UPDATE jobs SET status='QUEUED',fencing_token=fencing_token+1,lease_owner=NULL,lease_expires_at=NULL,error_json=NULL,updated_at=? WHERE job_id=?", (time.time(),job_id))
            self._event(connection,job_id,"JOB_LOCAL_RETRY_REQUESTED",{"previous_attempt":expected_attempt,"requested_by":requested_by})
            connection.commit()
        return self.get(job_id)

    def cancel(self, job_id: str) -> JobRecord:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            target = {"QUEUED": "CANCELLED", "RUNNING": "CANCEL_REQUESTED"}.get(row[0])
            if target:
                conn.execute("UPDATE jobs SET status=?,updated_at=? WHERE job_id=?", (target, time.time(), job_id))
                self._event(conn, job_id, "JOB_" + target, {})
            conn.commit()
        return self.get(job_id)
