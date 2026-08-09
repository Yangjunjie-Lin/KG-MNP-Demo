"""Stable output contracts for assessment results."""

from __future__ import annotations

from typing import Any

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from kg_mnp_demo.modeling.dependencies import ROOT

SCHEMA_VERSION = "1.0"

APPLICATION_SCHEMAS = {
    "query-request": ("query_request.schema.json", "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/application/query-request/1.0"),
    "query-result": ("query_result.schema.json", "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/application/query-result/1.0"),
    "entity-view": ("entity_view.schema.json", "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/application/entity-view/1.0"),
    "traceability-result": ("traceability_result.schema.json", "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/application/traceability-result/1.0"),
    "error-response": ("error_response.schema.json", "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/application/error-response/1.0"),
    "application-phase01-attestation": ("application_phase01_attestation.schema.json", "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/application/application-phase01-attestation/1.0"),
}


def _unique_schema_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_application_schema(name: str, root: Path = ROOT) -> dict[str, Any]:
    if name not in APPLICATION_SCHEMAS:
        raise ValueError(f"unknown application contract: {name}")
    filename, identifier = APPLICATION_SCHEMAS[name]
    document = json.loads(
        (Path(root) / "schemas/application" / filename).read_text(encoding="utf-8"),
        object_pairs_hook=_unique_schema_object,
    )
    if document.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or document.get("$id") != identifier:
        raise ValueError(f"invalid application schema: {name}")
    Draft202012Validator.check_schema(document)
    return document


def validate_application_contract(name: str, payload: Any, root: Path = ROOT) -> None:
    errors = sorted(
        Draft202012Validator(
            load_application_schema(name, root), format_checker=FormatChecker()
        ).iter_errors(payload),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise ValueError(f"{name}: {errors[0].message}")

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
