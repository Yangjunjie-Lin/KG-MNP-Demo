"""Frozen core result models; authoritative JSON remains contract-validated."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceRegistrationResult:
    source: dict[str, Any]
    duplicate: bool


@dataclass(frozen=True)
class PlanResult:
    plan: dict[str, Any]
    path: Path


@dataclass(frozen=True)
class IngestionResult:
    run: dict[str, Any]
    dataset: dict[str, Any]
    quality_report: dict[str, Any]


@dataclass(frozen=True)
class EvidenceBundle:
    evidence_records: tuple[dict[str, Any], ...]
    transformation_records: tuple[dict[str, Any], ...]
