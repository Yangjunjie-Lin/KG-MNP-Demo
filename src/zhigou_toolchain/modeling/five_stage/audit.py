"""Immutable before/after observations, not an execution or approval authority."""
from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.delivery.exchange_io import atomic_file, json_bytes
from zhigou_toolchain.modeling.delivery.trace import public_value

ACTIVE_AUDIT: ContextVar[StepAudit | None] = ContextVar("ontology_step_audit", default=None)


class StepAudit:
    """One directory per real job attempt; each event is written before continuing.

    Content is opt-in and redacted. Metadata remains available without recording
    sources. No old events are reconstructed from output hashes.
    """

    def __init__(self, directory, binding, *, content=False):
        self.directory = directory
        self.binding = binding
        self.content = content
        self.sequence = 0
        self.previous = None
        self.lock = RLock()
        self.pending = {}
        self.computed_state: dict | None = None
        self.bytes_written = 0
        self.calls = {}

    def emit(self, phase, call_id, *, metadata, value=None):
        with self.lock:
            changes = set()
            payload = {"semantic_sha256": semantic_hash(value), "capture": "METADATA_ONLY"}
            if self.content:
                safe = public_value(value, changes)
                if len(json_bytes(safe)) <= 4_000_000:
                    payload.update(value=safe, capture="REDACTED" if changes else "CAPTURED", redactions=sorted(changes))
                else:
                    payload.update(capture="OMITTED_SIZE_LIMIT", reason="Content exceeds 4 MB; digest retained")
            row = {"format": "zhigou-step-audit-event/1.0.0", "sequence": self.sequence + 1,
                   "phase": phase, "call_id": call_id, "ts": datetime.now(UTC).isoformat(),
                   "binding": self.binding, "metadata": metadata, "payload": payload,
                   "previous_event_sha256": self.previous}
            row["event_sha256"] = semantic_hash(row)
            raw = json_bytes(row)
            if self.sequence >= 20000 or self.bytes_written + len(raw) > 64_000_000:
                raise ValueError("STEP_AUDIT_LIMIT")
            atomic_file(self.directory / f"{row['sequence']:06d}-{phase.lower()}.json", raw)
            self.bytes_written += len(raw)
            self.sequence += 1
            self.previous = row["event_sha256"]
            return row

    def before(self, metadata, value):
        call_id = uuid4().hex
        # Freeze metadata now, including dependencies; callers may mutate them.
        metadata = json.loads(json_bytes(metadata))
        event = self.emit("BEFORE", call_id, metadata=metadata, value=value)
        self.pending[call_id] = metadata
        self.calls[call_id] = {"call_id": call_id, **metadata, "status": "STARTED", "before_event_sha256": event["event_sha256"]}
        return call_id

    def after(self, call_id, value=None, *, status, error=None, outcome=None):
        metadata = {**self.pending[call_id], "status": status, **(outcome or {})}
        if error is not None:
            # Never persist arbitrary exception messages containing source data.
            metadata["error"] = {"type": type(error).__name__}
            code = getattr(error, "code", None)
            if isinstance(code, str) and code.replace("_", "").isalnum() and code.upper() == code:
                metadata["error"]["code"] = code
        event = self.emit("AFTER", call_id, metadata=metadata, value=value)
        self.calls[call_id].update(metadata)
        del self.pending[call_id]
        return event["event_sha256"]

    def close_index(self):
        atomic_file(self.directory / "summary.json", json_bytes({"binding": self.binding,
            "event_count": self.sequence, "final_event_sha256": self.previous,
            "stages": sorted({c["stage_id"] for c in self.calls.values()}),
            "content_mode": "REDACTED_CONTENT" if self.content else "METADATA_ONLY"}))
