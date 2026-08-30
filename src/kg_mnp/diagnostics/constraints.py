"""Faithful projection of formal validation results into diagnostics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .authority_binding import AuthorityBindings
from .issue import DiagnosticIssue
from .policy import shacl_classification


def _field(record: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in record:
            return record[name]
    return None


def _projected(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    term_type = value.get("term_type")
    if term_type == "IRI":
        return value.get("value", value.get("iri"))
    if term_type == "STRUCTURAL_NODE":
        return value.get("stable_id")
    if term_type == "LITERAL":
        return dict(value)
    return value


def diagnostics_from_constraint_results(
    results: Iterable[Mapping[str, Any]],
    *,
    bindings: AuthorityBindings,
    module: str = "verified-shacl",
) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    for result in results:
        focus = _projected(_field(result, "focus_node", "focusNode"))
        path = _projected(_field(result, "result_path", "resultPath", "path"))
        severity_raw = str(_projected(_field(result, "severity")) or "")
        source_shape = _projected(_field(result, "source_shape", "sourceShape"))
        component = _projected(_field(
            result,
            "source_constraint_component",
            "sourceConstraintComponent",
        ))
        if focus is None or source_shape is None or not severity_raw:
            raise ValueError("formal constraint result lacks required authority fields")
        classification = shacl_classification(severity_raw)
        severity = severity_raw.rsplit("#", 1)[-1]
        constraint_result = {
            "source_shape": str(source_shape),
            "source_constraint_component": (
                str(component) if component is not None else None
            ),
            "severity": severity,
            "message": (
                str(_field(result, "message", "resultMessage"))
                if _field(result, "message", "resultMessage") is not None
                else None
            ),
            "value": _projected(_field(result, "value")),
            "named_graph": (
                str(_field(result, "named_graph", "source_context"))
                if _field(result, "named_graph", "source_context") is not None
                else None
            ),
        }
        basis = {
            "requirement_type": "SHACL_VALIDATION_RESULT",
            "authority_iri": str(component or source_shape),
            "shape_iri": str(source_shape),
            "constraint_iri": str(component) if component is not None else None,
            "module": module,
            "publication_id": bindings.publication_id,
        }
        issues.append(
            DiagnosticIssue.create(
                classification=classification,
                focus_node=str(focus),
                path=str(path) if path is not None else None,
                authority_basis=[basis],
                bindings=bindings,
                observed_values=(
                    [constraint_result["value"]]
                    if constraint_result["value"] is not None
                    else []
                ),
                constraint_result=constraint_result,
            )
        )
    return issues


detect_constraint_diagnostics = diagnostics_from_constraint_results
