"""Stable output contracts for assessment results."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "1.0"

ASSESSMENT_RESPONSE_KEYS = (
    "schema_version",
    "execution_id",
    "case_id",
    "assessment_time",
    "decision",
    "publication",
    "validations",
    "input_summary",
    "evidence",
    "rule_results",
    "blocking_reasons",
    "remediation_actions",
    "process",
    "trace_subgraph",
    "inference",
    "warnings",
    "artifacts",
)


def empty_validation(label: str, *, status: str = "SKIPPED") -> dict[str, Any]:
    return {
        "label": label,
        "status": status,
        "conforms": status == "PASSED",
        "detail": "",
    }


def empty_process() -> dict[str, Any]:
    return {
        "current_step": None,
        "next_step": None,
        "can_advance": False,
        "blocking_reasons": [],
        "authorization_code": None,
    }


def empty_trace() -> dict[str, Any]:
    return {"nodes": [], "edges": []}


def build_assessment_response(
    *,
    execution_id: str,
    case_id: str | None,
    assessment_time: str | None,
    decision: str | None,
    publication: dict[str, Any],
    validations: dict[str, Any],
    input_summary: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    rule_results: list[dict[str, Any]] | None = None,
    blocking_reasons: list[dict[str, Any]] | None = None,
    remediation_actions: list[dict[str, Any]] | None = None,
    process: dict[str, Any] | None = None,
    trace_subgraph: dict[str, Any] | None = None,
    inference: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    artifacts: dict[str, Any] | None = None,
    schema_version: str = SCHEMA_VERSION,
) -> dict[str, Any]:
    """Build a stable assessment response with deterministic key order."""
    return {
        "schema_version": schema_version,
        "execution_id": execution_id,
        "case_id": case_id,
        "assessment_time": assessment_time,
        "decision": decision,
        "publication": publication,
        "validations": validations,
        "input_summary": input_summary or {},
        "evidence": evidence or [],
        "rule_results": rule_results or [],
        "blocking_reasons": blocking_reasons or [],
        "remediation_actions": remediation_actions or [],
        "process": process if process is not None else empty_process(),
        "trace_subgraph": trace_subgraph if trace_subgraph is not None else empty_trace(),
        "inference": inference or {},
        "warnings": warnings or [],
        "artifacts": artifacts or {},
    }
