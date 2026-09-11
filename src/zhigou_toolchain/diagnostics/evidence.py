"""Evidence gaps derived only from explicit frozen requirements."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .authority_binding import AuthorityBindings
from .issue import DiagnosticIssue
from .policy import DiagnosticClassification
from .requirement_index import RequirementIndex, normalized_facts


def detect_evidence_gaps(
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
        if not requirement.evidence_required:
            continue
        for assertion in indexed.get(
            (requirement.focus_node, requirement.path), []
        ):
            evidence = assertion["evidence_refs"]
            if len(evidence) >= requirement.evidence_min_count:
                continue
            issues.append(
                DiagnosticIssue.create(
                    classification=DiagnosticClassification.EVIDENCE_REQUIRED_MISSING,
                    focus_node=requirement.focus_node,
                    path=requirement.path,
                    authority_basis=[requirement.authority_basis()],
                    bindings=bindings,
                    observed_values=[assertion["value"]],
                    source_assertions=[assertion["assertion_ref"]],
                    evidence_refs=evidence,
                    source_refs=assertion["source_refs"],
                    template_parameters={
                        "required_count": requirement.evidence_min_count,
                        "observed_count": len(evidence),
                    },
                )
            )
        for candidate in candidate_values:
            focus = str(candidate.get("focus_node") or candidate.get("subject"))
            path = str(candidate.get("path") or candidate.get("predicate"))
            if (focus, path) != (requirement.focus_node, requirement.path):
                continue
            evidence = sorted({str(value) for value in candidate.get("evidence_refs", [])})
            if len(evidence) >= requirement.evidence_min_count:
                continue
            issues.append(
                DiagnosticIssue.create(
                    classification=DiagnosticClassification.EVIDENCE_REQUIRED_MISSING,
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
                    evidence_refs=evidence,
                    source_refs=candidate.get("source_refs", []),
                    template_parameters={
                        "required_count": requirement.evidence_min_count,
                        "observed_count": len(evidence),
                    },
                )
            )
    return issues


evaluate_evidence = detect_evidence_gaps
