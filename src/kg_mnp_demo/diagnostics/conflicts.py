"""Conflict reconstruction requiring explicit incompatibility authority."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .authority_binding import AuthorityBindings
from .issue import DiagnosticIssue
from .policy import DiagnosticClassification, DiagnosticScope
from .requirement_index import RequirementIndex, normalized_facts


@dataclass(frozen=True)
class ConflictRule:
    focus_node: str
    path: str
    rule_type: str
    authority_iri: str
    module: str
    publication_id: str
    shape_iri: str | None = None
    constraint_iri: str | None = None
    max_count: int | None = None
    incompatible_values: tuple[Any, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ConflictRule":
        rule_type = str(value["rule_type"])
        allowed = {
            "FORMAL_MAX_COUNT",
            "OWL_FUNCTIONAL_PROPERTY",
            "OWL_DISJOINT_CLASSES",
            "EXPLICIT_MUTUAL_EXCLUSIVITY",
        }
        if rule_type not in allowed:
            raise ValueError("unsupported formal conflict rule")
        if not all(
            isinstance(value.get(field), str) and value.get(field)
            for field in (
                "focus_node",
                "path",
                "authority_iri",
                "module",
                "publication_id",
            )
        ):
            raise ValueError("formal conflict rule identity is incomplete")
        incompatible = tuple(value.get("incompatible_values", ()))
        max_count = value.get("max_count")
        if rule_type in {"FORMAL_MAX_COUNT", "OWL_FUNCTIONAL_PROPERTY"}:
            max_count = 1 if max_count is None else int(max_count)
            if max_count < 0:
                raise ValueError("formal conflict max_count cannot be negative")
        elif len(incompatible) < 2:
            raise ValueError("exclusivity rules require at least two values")
        return cls(
            focus_node=str(value["focus_node"]),
            path=str(value["path"]),
            rule_type=rule_type,
            authority_iri=str(value["authority_iri"]),
            module=str(value["module"]),
            publication_id=str(value["publication_id"]),
            shape_iri=str(value["shape_iri"]) if value.get("shape_iri") else None,
            constraint_iri=(
                str(value["constraint_iri"])
                if value.get("constraint_iri")
                else None
            ),
            max_count=max_count,
            incompatible_values=incompatible,
        )

    def authority_basis(self) -> dict[str, Any]:
        return {
            "requirement_type": self.rule_type,
            "authority_iri": self.authority_iri,
            "shape_iri": self.shape_iri,
            "constraint_iri": self.constraint_iri,
            "module": self.module,
            "publication_id": self.publication_id,
        }


def detect_confirmed_conflicts(
    requirements: RequirementIndex,
    facts: Iterable[Mapping[str, Any]],
    *,
    bindings: AuthorityBindings,
    rules: Iterable[ConflictRule | Mapping[str, Any]] = (),
) -> list[DiagnosticIssue]:
    indexed = normalized_facts(facts)
    issues: list[DiagnosticIssue] = []
    for requirement in requirements:
        if requirement.max_count is None:
            continue
        current = indexed.get((requirement.focus_node, requirement.path), [])
        distinct: dict[str, Any] = {}
        for record in current:
            distinct.setdefault(semantic_hash(record["value"]), record["value"])
        if len(distinct) <= requirement.max_count:
            continue
        issues.append(
            DiagnosticIssue.create(
                classification=DiagnosticClassification.CONFIRMED_VALUE_CONFLICT,
                focus_node=requirement.focus_node,
                path=requirement.path,
                authority_basis=[requirement.authority_basis()],
                bindings=bindings,
                observed_values=distinct.values(),
                source_assertions=(record["assertion_ref"] for record in current),
            )
        )
    for supplied in rules:
        rule = supplied if isinstance(supplied, ConflictRule) else ConflictRule.from_dict(supplied)
        current = indexed.get((rule.focus_node, rule.path), [])
        distinct = {semantic_hash(record["value"]): record["value"] for record in current}
        conflicting: list[Any]
        if rule.max_count is not None:
            conflicting = list(distinct.values()) if len(distinct) > rule.max_count else []
        else:
            allowed = {semantic_hash(value) for value in rule.incompatible_values}
            conflicting = [value for digest, value in distinct.items() if digest in allowed]
            if len(conflicting) < 2:
                conflicting = []
        if not conflicting:
            continue
        issues.append(
            DiagnosticIssue.create(
                classification=DiagnosticClassification.CONFIRMED_VALUE_CONFLICT,
                focus_node=rule.focus_node,
                path=rule.path,
                authority_basis=[rule.authority_basis()],
                bindings=bindings,
                observed_values=conflicting,
                source_assertions=(record["assertion_ref"] for record in current),
            )
        )
    return issues


def _candidate_basis(
    candidate: Mapping[str, Any],
    *,
    bindings: AuthorityBindings,
) -> dict[str, Any]:
    supplied = candidate.get("authority_basis")
    if isinstance(supplied, list) and supplied and isinstance(supplied[0], Mapping):
        return dict(supplied[0])
    decision_ref = str(
        candidate.get("_decision_ref")
        or candidate.get("review_decision_ref")
        or candidate.get("review_ref")
        or candidate.get("candidate_ref")
    )
    return {
        "requirement_type": "FROZEN_REVIEW_HISTORY",
        "authority_iri": decision_ref,
        "shape_iri": None,
        "constraint_iri": None,
        "module": "review-audit",
        "publication_id": bindings.publication_id,
    }


def detect_candidate_history(
    candidates: Iterable[Mapping[str, Any]],
    *,
    bindings: AuthorityBindings,
) -> list[DiagnosticIssue]:
    normalized = [dict(value) for value in candidates]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    issues: list[DiagnosticIssue] = []
    for candidate in normalized:
        focus = str(candidate.get("focus_node") or candidate.get("subject"))
        path = str(candidate.get("path") or candidate.get("predicate"))
        candidate_ref = str(
            candidate.get("candidate_ref")
            or candidate.get("candidate_id")
            or f"urn:kg-mnp:candidate:{semantic_hash(candidate)}"
        )
        decision_ref = str(
            candidate.get("review_decision_ref")
            or candidate.get("review_ref")
            or f"urn:kg-mnp:review-decision:{semantic_hash([candidate_ref, candidate.get('outcome')])}"
        )
        candidate["_focus"] = focus
        candidate["_path"] = path
        candidate["_candidate_ref"] = candidate_ref
        candidate["_decision_ref"] = decision_ref
        grouped[(focus, path)].append(candidate)
        outcome = str(
            candidate.get("outcome", candidate.get("review_outcome", ""))
        ).upper()
        classification = {
            "REJECT": DiagnosticClassification.REJECTED_CANDIDATE_HISTORY,
            "REJECTED": DiagnosticClassification.REJECTED_CANDIDATE_HISTORY,
            "DEFER": DiagnosticClassification.DEFERRED_CANDIDATE_HISTORY,
            "DEFERRED": DiagnosticClassification.DEFERRED_CANDIDATE_HISTORY,
        }.get(outcome)
        if classification is not None:
            issues.append(
                DiagnosticIssue.create(
                    classification=classification,
                    focus_node=focus,
                    path=path,
                    authority_basis=[_candidate_basis(candidate, bindings=bindings)],
                    bindings=bindings,
                    observed_values=[candidate.get("value")],
                    candidate_refs=[candidate_ref],
                    review_decision_refs=[decision_ref],
                    evidence_refs=candidate.get("evidence_refs", []),
                    source_refs=candidate.get("source_refs", []),
                    scope=DiagnosticScope.HISTORICAL_REVIEW_CONTEXT,
                )
            )
    for (focus, path), values in grouped.items():
        distinct = {semantic_hash(value.get("value")) for value in values}
        was_conflict = any(value.get("review_conflict") is True for value in values)
        if len(distinct) < 2 or not was_conflict:
            continue
        authority = [_candidate_basis(value, bindings=bindings) for value in values]
        issues.append(
            DiagnosticIssue.create(
                classification=DiagnosticClassification.HISTORICAL_REVIEW_CONFLICT,
                focus_node=focus,
                path=path,
                authority_basis=authority,
                bindings=bindings,
                observed_values=[value.get("value") for value in values],
                candidate_refs=[value["_candidate_ref"] for value in values],
                review_decision_refs=[value["_decision_ref"] for value in values],
                scope=DiagnosticScope.HISTORICAL_REVIEW_CONTEXT,
            )
        )
    return issues


detect_conflicts = detect_confirmed_conflicts
