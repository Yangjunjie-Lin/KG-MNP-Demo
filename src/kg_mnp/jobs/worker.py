from __future__ import annotations

from threading import Event, Thread
from typing import Any

from kg_mnp.services.errors import ServiceBoundaryError

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
            while not stopped.wait(10):
                try:
                    self.store.renew(job.job_id, worker_id=worker_id, fencing_token=job.fencing_token)
                except ValueError:
                    return

        heartbeat = Thread(target=renew, daemon=True)
        heartbeat.start()
        try:
            result = self.executor.execute_job(job, self.store.parameters(job.job_id))
            return self.store.complete(job.job_id, worker_id=worker_id, fencing_token=job.fencing_token, result=result)
        except Exception as exc:  # noqa: BLE001 - failure is persisted for recovery
            error = {"code": exc.code if isinstance(exc, ServiceBoundaryError) else "JOB_EXECUTION_FAILED",
                     "message": exc.message if isinstance(exc, ServiceBoundaryError) else "job execution failed"}
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
