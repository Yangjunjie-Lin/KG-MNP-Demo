from __future__ import annotations

import json
from pathlib import Path
from time import time
from uuid import uuid4

from kg_mnp.contracts.canonical import semantic_hash


class AuditLog:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, *, principal_id: str, operation_id: str, project_id: str | None, request_id: str, outcome: str, details: dict) -> str:
        rows = []
        if self.path.is_file():
            rows = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        audit_id = "audit_" + uuid4().hex
        row = {"audit_id": audit_id, "observed_at": time(), "principal_id": principal_id, "operation_id": operation_id, "project_id": project_id, "request_id": request_id, "outcome": outcome, "details": details, "previous_hash": rows[-1]["content_hash"] if rows else None}
        row["content_hash"] = semantic_hash(row)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return audit_id
