from __future__ import annotations

from typing import Any

from .store import JobStore


class JobWorker:
    def __init__(self, store: JobStore, executor: Any):
        self.store = store
        self.executor = executor

    def run_once(self, worker_id: str = "worker"):
        job = self.store.claim(worker_id=worker_id)
        if job is None:
            return None
        try:
            result = self.executor.execute_job(job, self.store.parameters(job.job_id))
            return self.store.complete(job.job_id, worker_id=worker_id, fencing_token=job.fencing_token, result=result)
        except Exception as exc:  # noqa: BLE001 - failure is persisted for recovery
            return self.store.fail(job.job_id, worker_id=worker_id, fencing_token=job.fencing_token, error={"code": type(exc).__name__, "message": str(exc)})
