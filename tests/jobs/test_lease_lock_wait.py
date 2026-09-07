"""Waiting for SQLite writer ownership must not resurrect an expired lease."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from kg_mnp.jobs.store import JobStore


def test_renew_checks_time_after_writer_lock_wait(tmp_path, monkeypatch):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.create(operation_id="test", project_id="synthetic", parameters={})
    job = store.claim(worker_id="old", lease_seconds=1)
    clock = [job.lease_expires_at - 0.5]
    entered = Event()
    def now():
        entered.set()
        return clock[0]
    monkeypatch.setattr("kg_mnp.jobs.store.time.time", now)
    lock = sqlite3.connect(store.path, isolation_level=None)
    lock.execute("BEGIN IMMEDIATE")
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(store.renew, job.job_id, worker_id="old", fencing_token=job.fencing_token)
        # On the buggy implementation this is called before the blocking UPDATE.
        entered.wait(0.1)
        clock[0] = job.lease_expires_at + 1
        lock.commit()
        lock.close()
        with pytest.raises(ValueError, match="stale"):
            pending.result(timeout=5)
    assert store.get(job.job_id).lease_expires_at == job.lease_expires_at
