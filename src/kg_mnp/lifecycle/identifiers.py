"""Deterministic identifiers used by the offline lifecycle control plane."""
from __future__ import annotations

from typing import Any

from kg_mnp.contracts.canonical import semantic_hash, stable_urn


def content_digest(value: Any) -> str:
    return semantic_hash(value)


def artifact_id(kind: str, value: Any) -> str:
    return stable_urn(kind, {"content_digest": content_digest(value)})


def event_id(semantic_event_hash: str) -> str:
    return stable_urn("registry-event", {"semantic_event_hash": semantic_event_hash})


__all__ = ["artifact_id", "content_digest", "event_id"]
