from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    operation_id: str
    project_id: str | None
    request_digest: str
    status: str
    attempt: int
    fencing_token: int
    lease_owner: str | None
    lease_expires_at: float | None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


@dataclass(frozen=True)
class JobEvent:
    job_id: str
    sequence: int
    event_type: str
    payload: dict[str, Any]
    observed_at: float
