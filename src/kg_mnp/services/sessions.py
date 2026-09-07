"""Short-lived opaque browser sessions referencing the one TokenStore authority."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time

from .errors import ServiceBoundaryError


class SessionStore:
    def __init__(self, path, tokens):
        self.path, self.tokens = path, tokens
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, token_id TEXT NOT NULL, "
                         "csrf_token TEXT NOT NULL, expires_at REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)")

    def create(self, principal, lifetime=1800):
        if not principal.token_id:
            raise ServiceBoundaryError("AUTH_REQUIRED", "server credential required", status_code=401)
        self.tokens.resolve(principal.token_id)
        opaque, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO sessions(digest,token_id,csrf_token,expires_at) VALUES(?,?,?,?)",
                         (hashlib.sha256(opaque.encode()).hexdigest(), principal.token_id, csrf, time.time() + lifetime))
        return opaque, csrf

    def resolve(self, opaque):
        if not opaque or len(opaque) > 100:
            raise ServiceBoundaryError("SESSION_REQUIRED", "browser session required", status_code=401)
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT token_id,csrf_token,expires_at,revoked FROM sessions WHERE digest=?",
                               (hashlib.sha256(opaque.encode()).hexdigest(),)).fetchone()
        if not row or row[3] or row[2] <= time.time():
            raise ServiceBoundaryError("SESSION_EXPIRED", "browser session expired or revoked", status_code=401)
        return self.tokens.resolve(row[0]), row[1]

    def revoke(self, opaque):
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE sessions SET revoked=1 WHERE digest=?", (hashlib.sha256(opaque.encode()).hexdigest(),))
