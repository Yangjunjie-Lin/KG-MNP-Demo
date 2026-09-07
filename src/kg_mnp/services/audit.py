from __future__ import annotations

import json
import os
from pathlib import Path
from time import time
from uuid import uuid4

from kg_mnp.contracts.canonical import semantic_hash

from .coordination import metadata_lock
from .errors import ServiceBoundaryError


class AuditLog:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, *, principal_id: str, operation_id: str, project_id: str | None, request_id: str, outcome: str, details: dict) -> str:
        with metadata_lock(self.path.with_suffix(".lock.sqlite3")):
            previous=None
            if self.path.is_file() and self.path.stat().st_size:
                with self.path.open("rb") as stream:
                    stream.seek(max(0,self.path.stat().st_size-131072))
                    tail=stream.read().rstrip(b"\r\n").rsplit(b"\n",1)[-1]
                try:
                    prior=json.loads(tail)
                    if prior["content_hash"]!=semantic_hash({k:v for k,v in prior.items() if k!="content_hash"}):raise ValueError("hash")
                    previous=prior["content_hash"]
                except (ValueError,KeyError) as exc:
                    raise ServiceBoundaryError("AUDIT_RECOVERY_REQUIRED","audit tail is invalid; no automatic rewrite",status_code=503) from exc
            audit_id = "audit_" + uuid4().hex
            row = {"audit_id": audit_id, "observed_at": time(), "principal_id": principal_id, "operation_id": operation_id, "project_id": project_id, "request_id": request_id, "outcome": outcome, "details": details, "previous_hash": previous}
            row["content_hash"] = semantic_hash(row)
            payload=(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n").encode("utf8")
            if len(payload)>65536:raise ServiceBoundaryError("AUDIT_EVENT_TOO_LARGE","audit event exceeds limit",status_code=422)
            with self.path.open("ab") as stream:
                stream.write(payload);stream.flush();os.fsync(stream.fileno())
            return audit_id

    def verify(self):
        with metadata_lock(self.path.with_suffix(".lock.sqlite3")):
            previous=None;count=0
            if self.path.exists():
                try:
                    with self.path.open("rb") as stream:
                        for line in stream:
                            row=json.loads(line)
                            if row["previous_hash"]!=previous or row["content_hash"]!=semantic_hash({k:v for k,v in row.items() if k!="content_hash"}):
                                raise ValueError("audit chain")
                            previous=row["content_hash"];count+=1
                except (ValueError,KeyError):return {"status":"RECOVERY_REQUIRED","verified_records":count}
            return {"status":"VALID","verified_records":count,"head_hash":previous}
