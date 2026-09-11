"""Deterministic, evidence-bound ingestion kernel (not ontology modeling)."""

from .limits import DEFAULT_LIMITS
from .planner import create_ingestion_plan
from .source_store import SourceStore

__all__ = ["DEFAULT_LIMITS", "SourceStore", "create_ingestion_plan"]
