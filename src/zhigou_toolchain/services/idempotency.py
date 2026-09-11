"""Durable synchronous idempotency; ambiguous outcomes are never retried blindly."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash

from .errors import ServiceBoundaryError


class IdempotencyStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS requests (scope TEXT PRIMARY KEY, digest TEXT NOT NULL, status TEXT NOT NULL, result TEXT)")

    def execute(self, request, principal, action):
        if not request.idempotency_key:
            return action()
        scope = semantic_hash({"principal": principal.principal_id, "project": request.project_id,
                               "operation": request.operation_id, "key": request.idempotency_key})
        digest = semantic_hash(request.parameters)
        with sqlite3.connect(self.path, timeout=30) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT digest,status,result FROM requests WHERE scope=?", (scope,)).fetchone()
            if row:
                if row[0] != digest:
                    raise ServiceBoundaryError("IDEMPOTENCY_CONFLICT", "idempotency key was reused with a different request", status_code=409)
                if row[1] == "SUCCEEDED":
                    return json.loads(row[2])
                if row[1] == "FAILED":
                    saved = json.loads(row[2])
                    raise ServiceBoundaryError(**saved)
                raise ServiceBoundaryError("RECOVERY_REQUIRED", "previous request is in progress or its outcome is unknown; do not resubmit with a new key", status_code=409)
            # Commit intent BEFORE entering a filesystem mutation. A crash after
            # its commit retains ambiguity instead of silently duplicating it.
            conn.execute("INSERT INTO requests VALUES(?,?,?,NULL)", (scope, digest, "RECOVERY_REQUIRED"))
        try:
            result = action()
        except ServiceBoundaryError as exc:
            saved = {"code": exc.code, "message": exc.message, "status_code": exc.status_code, "retryable": exc.retryable}
            self._finish(scope, "FAILED", saved)
            raise
        self._finish(scope, "SUCCEEDED", result)
        return result

    def _finish(self, scope, status, result):
        with sqlite3.connect(self.path, timeout=30) as conn:
            conn.execute("UPDATE requests SET status=?,result=? WHERE scope=?", (status, json.dumps(result, sort_keys=True), scope))
