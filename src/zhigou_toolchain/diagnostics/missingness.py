"""Open-world-safe required, optional, unknown and uncertain diagnostics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .authority_binding import AuthorityBindings
from .issue import DiagnosticIssue
from .policy import DiagnosticClassification
from .requirement_index import RequirementIndex, normalized_facts


def detect_missingness(
    requirements: RequirementIndex,
    facts: Iterable[Mapping[str, Any]],
    *,
    bindings: AuthorityBindings,
) -> list[DiagnosticIssue]:
    indexed = normalized_facts(facts)
    issues: list[DiagnosticIssue] = []
    for requirement in requirements:
        current = indexed.get((requirement.focus_node, requirement.path), [])
        values = [record["value"] for record in current]
        assertions = [record["assertion_ref"] for record in current]
        if requirement.min_count > len(current):
            issues.append(
                DiagnosticIssue.create(
                    classification=DiagnosticClassification.REQUIRED_VALUE_MISSING,
                    focus_node=requirement.focus_node,
                    path=requirement.path,
                    authority_basis=[requirement.authority_basis()],
                    bindings=bindings,
                    observed_values=values,
                    source_assertions=assertions,
                )
            )
        elif not current and requirement.report_optional_absence:
            issues.append(
                DiagnosticIssue.create(
                    classification=DiagnosticClassification.OPTIONAL_VALUE_ABSENT,
                    focus_node=requirement.focus_node,
                    path=requirement.path,
                    authority_basis=[requirement.authority_basis()],
                    bindings=bindings,
                )
            )
        for record in current:
            state = record["value_state"]
            classification = {
                "UNKNOWN": DiagnosticClassification.VALUE_UNKNOWN,
                "UNCERTAIN": DiagnosticClassification.VALUE_UNCERTAIN,
                "NOT_APPLICABLE": DiagnosticClassification.VALUE_NOT_APPLICABLE,
            }.get(state)
            if classification is not None:
                issues.append(
                    DiagnosticIssue.create(
                        classification=classification,
                        focus_node=requirement.focus_node,
                        path=requirement.path,
                        authority_basis=[requirement.authority_basis()],
                        bindings=bindings,
                        observed_values=[record["value"]],
                        source_assertions=[record["assertion_ref"]],
                    )
                )
    return issues


evaluate_missingness = detect_missingness
