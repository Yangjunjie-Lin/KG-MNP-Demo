"""Pure reconstruction of diagnostics from a verified authority snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from .authority_binding import AuthorityBindings
from .conflicts import ConflictRule, detect_candidate_history, detect_confirmed_conflicts
from .constraints import diagnostics_from_constraint_results
from .evidence import detect_evidence_gaps
from .missingness import detect_missingness
from .package import DeterministicDiagnosticPackage, build_diagnostic_package
from .requirement_index import RequirementIndex, normalized_facts
from .sources import detect_source_gaps


@dataclass(frozen=True)
class AuthoritySnapshot:
    authority_bindings: AuthorityBindings
    requirements: tuple[Mapping[str, Any], ...]
    facts: tuple[Mapping[str, Any], ...]
    constraint_results: tuple[Mapping[str, Any], ...] = ()
    candidates: tuple[Mapping[str, Any], ...] = ()
    conflict_rules: tuple[Mapping[str, Any], ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AuthoritySnapshot":
        allowed = {
            "authority_bindings",
            "requirements",
            "facts",
            "constraint_results",
            "candidates",
            "conflict_rules",
        }
        if set(value) - allowed or not {
            "authority_bindings",
            "requirements",
            "facts",
        } <= set(value):
            raise ValueError("authority snapshot field set mismatch")
        return cls(
            authority_bindings=AuthorityBindings.from_dict(value["authority_bindings"]),
            requirements=tuple(deepcopy(value["requirements"])),
            facts=tuple(deepcopy(value["facts"])),
            constraint_results=tuple(deepcopy(value.get("constraint_results", []))),
            candidates=tuple(deepcopy(value.get("candidates", []))),
            conflict_rules=tuple(deepcopy(value.get("conflict_rules", []))),
        )


def _order_independent(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _order_independent(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        normalized = [_order_independent(item) for item in value]
        return sorted(normalized, key=canonical_json_bytes)
    return value


def authority_snapshot_semantic_hash(snapshot: AuthoritySnapshot) -> str:
    return semantic_hash(
        _order_independent(
            {
                "authority_bindings": snapshot.authority_bindings.to_dict(),
                "requirements": snapshot.requirements,
                "facts": snapshot.facts,
                "constraint_results": snapshot.constraint_results,
                "candidates": snapshot.candidates,
                "conflict_rules": snapshot.conflict_rules,
            }
        )
    )


def reconstruct_diagnostics(
    snapshot: AuthoritySnapshot | Mapping[str, Any],
) -> DeterministicDiagnosticPackage:
    authority = (
        snapshot if isinstance(snapshot, AuthoritySnapshot) else AuthoritySnapshot.from_dict(snapshot)
    )
    requirements = RequirementIndex(authority.requirements)
    facts = list(authority.facts)
    bindings = authority.authority_bindings
    if any(
        requirement.publication_id != bindings.publication_id
        for requirement in requirements
    ):
        raise ValueError("requirement publication binding mismatch")
    formal_conflict_rules = [
        value if isinstance(value, ConflictRule) else ConflictRule.from_dict(value)
        for value in authority.conflict_rules
    ]
    if any(
        rule.publication_id != bindings.publication_id
        for rule in formal_conflict_rules
    ):
        raise ValueError("conflict rule publication binding mismatch")
    issues = [
        *detect_missingness(requirements, facts, bindings=bindings),
        *detect_confirmed_conflicts(
            requirements,
            facts,
            bindings=bindings,
            rules=formal_conflict_rules,
        ),
        *diagnostics_from_constraint_results(
            authority.constraint_results,
            bindings=bindings,
        ),
        *detect_candidate_history(authority.candidates, bindings=bindings),
        *detect_evidence_gaps(
            requirements,
            facts,
            bindings=bindings,
            candidates=authority.candidates,
        ),
        *detect_source_gaps(
            requirements,
            facts,
            bindings=bindings,
            candidates=authority.candidates,
        ),
    ]
    indexed = normalized_facts(facts)
    coverage = {
        "formal_requirement_count": len(requirements) + len(authority.conflict_rules),
        "requirements_evaluated": len(requirements) + len(authority.conflict_rules),
        "shacl_constraints_evaluated": len(authority.constraint_results),
        "focus_nodes_evaluated": len(requirements.focus_nodes),
        "confirmed_assertions_evaluated": sum(len(values) for values in indexed.values()),
        "review_decisions_considered": len(authority.candidates),
        "evidence_requirements_evaluated": sum(
            requirement.evidence_required for requirement in requirements
        ),
        "source_requirements_evaluated": sum(
            requirement.source_required for requirement in requirements
        ),
    }
    return build_diagnostic_package(
        issues,
        authority_bindings=bindings,
        coverage=coverage,
        diagnostic_basis_hash=authority_snapshot_semantic_hash(authority),
    )


build_diagnostics = reconstruct_diagnostics
