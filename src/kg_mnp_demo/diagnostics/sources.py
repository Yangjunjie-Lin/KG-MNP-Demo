"""Source gaps derived only from explicit frozen requirements."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .authority_binding import AuthorityBindings
from .issue import DiagnosticIssue
from .policy import DiagnosticClassification
from .requirement_index import RequirementIndex, normalized_facts


def detect_source_gaps(
    requirements: RequirementIndex,
    facts: Iterable[Mapping[str, Any]],
    *,
    bindings: AuthorityBindings,
    candidates: Iterable[Mapping[str, Any]] = (),
) -> list[DiagnosticIssue]:
    indexed = normalized_facts(facts)
    candidate_values = [dict(value) for value in candidates]
    issues: list[DiagnosticIssue] = []
    for requirement in requirements:
        if not requirement.source_required:
            continue
        for assertion in indexed.get(
            (requirement.focus_node, requirement.path), []
        ):
            sources = assertion["source_refs"]
            if len(sources) >= requirement.source_min_count:
                continue
            issues.append(
                DiagnosticIssue.create(
                    classification=DiagnosticClassification.SOURCE_REQUIRED_MISSING,
                    focus_node=requirement.focus_node,
                    path=requirement.path,
                    authority_basis=[requirement.authority_basis()],
                    bindings=bindings,
                    observed_values=[assertion["value"]],
                    source_assertions=[assertion["assertion_ref"]],
                    evidence_refs=assertion["evidence_refs"],
                    source_refs=sources,
                    template_parameters={
                        "required_count": requirement.source_min_count,
                        "observed_count": len(sources),
                    },
                )
            )
        for candidate in candidate_values:
            focus = str(candidate.get("focus_node") or candidate.get("subject"))
            path = str(candidate.get("path") or candidate.get("predicate"))
            if (focus, path) != (requirement.focus_node, requirement.path):
                continue
            sources = sorted({str(value) for value in candidate.get("source_refs", [])})
            if len(sources) >= requirement.source_min_count:
                continue
            issues.append(
                DiagnosticIssue.create(
                    classification=DiagnosticClassification.SOURCE_REQUIRED_MISSING,
                    focus_node=focus,
                    path=path,
                    authority_basis=[requirement.authority_basis()],
                    bindings=bindings,
                    observed_values=[candidate.get("value")],
                    candidate_refs=[
                        candidate.get("candidate_ref") or candidate.get("candidate_id")
                    ],
                    review_decision_refs=[
                        candidate.get("review_decision_ref") or candidate.get("review_ref")
                    ],
                    evidence_refs=candidate.get("evidence_refs", []),
                    source_refs=sources,
                    template_parameters={
                        "required_count": requirement.source_min_count,
                        "observed_count": len(sources),
                    },
                )
            )
    return issues


evaluate_sources = detect_source_gaps
