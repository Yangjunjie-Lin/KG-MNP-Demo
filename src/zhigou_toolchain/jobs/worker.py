from __future__ import annotations

import sqlite3
from threading import Event, Thread
from typing import Any

from zhigou_toolchain.services.errors import ServiceBoundaryError

from .store import JobStore


class JobWorker:
    def __init__(self, store: JobStore, executor: Any):
        self.store = store
        self.executor = executor

    def run_once(self, worker_id: str = "worker"):
        job = self.store.claim(worker_id=worker_id)
        if job is None:
            return None
        stopped = Event()

        def renew():
            delay = 10
            while not stopped.wait(delay):
                try:
                    self.store.renew(job.job_id, worker_id=worker_id, fencing_token=job.fencing_token)
                    delay = 10
                except ValueError:
                    return
                except sqlite3.OperationalError as exc:
                    if getattr(exc, "sqlite_errorcode", None) not in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                        raise
                    # Short contention can happen during a fenced publication.
                    # Retrying renewal grants no authority: expiry/token are
                    # rechecked after the writer lock is acquired each time.
                    delay = 1

        heartbeat = Thread(target=renew, daemon=True)
        heartbeat.start()
        try:
            result = self.executor.execute_job(job, self.store.parameters(job.job_id))
            return self.store.complete(job.job_id, worker_id=worker_id, fencing_token=job.fencing_token, result=result)
        except Exception as exc:  # noqa: BLE001 - failure is persisted for recovery
            if hasattr(self.executor, "recover_job"):
                recovered = self.executor.recover_job(job)
                if recovered is not None:
                    return recovered
            error = {"code": exc.code if isinstance(exc, ServiceBoundaryError) else "JOB_EXECUTION_FAILED",
                     "message": exc.message if isinstance(exc, ServiceBoundaryError) else "job execution failed",
                     "exception_type":type(exc).__name__,"errno":getattr(exc,"errno",None),"winerror":getattr(exc,"winerror",None)}
            try:
                return self.store.fail(job.job_id, worker_id=worker_id, fencing_token=job.fencing_token, error=error)
            except ValueError:
                # A stale worker cannot finish the replacement worker's job.
                return self.store.get(job.job_id)
        finally:
            stopped.set()
            heartbeat.join(timeout=2)

    def run_forever(self, worker_id: str = "worker", *, stop: Event | None = None):
        stopped = stop or Event()
        while not stopped.is_set():
            if self.run_once(worker_id) is None:
                stopped.wait(1)
