"""Deterministic, read-only registry audit projection."""
from __future__ import annotations

from pathlib import Path

from .registry.replay import verify_registry


def audit_registry(workspace: Path | str) -> dict:
    result = verify_registry(workspace)
    return {"status": result["status"], "registry_id": result["registry_id"], "event_count": result["event_count"], "snapshot_id": result["snapshot_id"]}


__all__ = ["audit_registry"]
