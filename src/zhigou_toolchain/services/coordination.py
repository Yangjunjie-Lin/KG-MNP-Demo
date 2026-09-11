"""Cross-process serialization for short local service metadata mutations.

SQLite releases locks on process death; no stale lockfile is auto-deleted.
These metadata locks do NOT constitute fencing for arbitrary core commits.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def metadata_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield
        connection.commit()
    finally:
        connection.close()
