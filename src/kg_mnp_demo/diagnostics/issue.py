"""Deterministic issue identifiers and template-only explanations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from .authority_binding import AuthorityBindings
from .contracts import validate_diagnostic_contract
from .policy import (
    POLICY_VERSION,
    DiagnosticClassification,
    DiagnosticScope,
    DiagnosticSeverity,
    classification_mapping,
)


def _sort_semantic(values: Iterable[Any]) -> list[Any]:
    copied = [deepcopy(value) for value in values]
    return sorted(copied, key=canonical_json_bytes)


def _references(values: Iterable[Any]) -> list[str]:
    return sorted(
        {
            str(value)
            for value in values
            if value is not None and str(value)
        }
    )


def _render(template_id: str, parameters: Mapping[str, Any]) -> str:
    focus = str(parameters.get("focus_node", "the focus node"))
    path = str(parameters.get("path", "the affected path"))
    authority = str(parameters.get("authority", "the cited authority"))
    templates = {
        "REQUIRED_PROPERTY_MISSING": (
            f"Required property {path} is not present for {focus} under constraint {authority}."
        ),
        "OPTIONAL_PROPERTY_ABSENT": (
            f"Optional property {path} is not asserted for {focus}; no negation is implied."
        ),
        "VALUE_UNKNOWN": f"The value of {path} for {focus} is explicitly unknown.",
        "VALUE_UNCERTAIN": f"The value of {path} for {focus} is explicitly uncertain.",
        "VALUE_NOT_APPLICABLE": f"The value of {path} for {focus} is explicitly not applicable.",
        "FORMAL_CONSTRAINT_RESULT": (
            f"A formal constraint result applies to {focus} at {path} under {authority}."
        ),
        "CONFIRMED_VALUE_CONFLICT": (
            f"Current confirmed values for {path} on {focus} violate {authority}."
        ),
        "HISTORICAL_REVIEW_CONFLICT": (
            f"Historical candidates for {path} on {focus} were in review conflict; this is not a current fact conflict."
        ),
        "REQUIRED_EVIDENCE_MISSING": (
            f"Required evidence for {focus} at {path} is missing under {authority}."
        ),
        "REQUIRED_SOURCE_MISSING": (
            f"Required source reference for {focus} at {path} is missing under {authority}."
        ),
        "REJECTED_CANDIDATE_HISTORY": (
            f"A rejected candidate for {path} on {focus} is retained only as review history."
        ),
        "DEFERRED_CANDIDATE_HISTORY": (
            f"A deferred candidate for {path} on {focus} is retained only as review history."
        ),
    }
    try:
        return templates[template_id]
    except KeyError as exc:
        raise ValueError(f"unknown diagnostic template: {template_id}") from exc


def diagnostic_semantic_basis(issue: Mapping[str, Any]) -> dict[str, Any]:
    excluded = {
        "contract_version",
        "diagnostic_id",
        "diagnostic_basis_hash",
        "explanation",
    }
    return {key: deepcopy(issue[key]) for key in sorted(issue) if key not in excluded}


def validate_diagnostic_identity(issue: Mapping[str, Any]) -> None:
    basis_hash = semantic_hash(diagnostic_semantic_basis(issue))
    if issue.get("diagnostic_basis_hash") != basis_hash:
        raise ValueError("diagnostic basis hash mismatch")
    if issue.get("diagnostic_id") != f"urn:kg-mnp:diagnostic:{basis_hash}":
        raise ValueError("diagnostic identifier mismatch")


@dataclass(frozen=True)
class DiagnosticIssue:
    value: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(dict(self.value))

    @property
    def diagnostic_id(self) -> str:
        return str(self.value["diagnostic_id"])

    @property
    def classification(self) -> str:
        return str(self.value["classification"])

    @classmethod
    def create(
        cls,
        *,
        classification: DiagnosticClassification | str,
        focus_node: str,
        path: str | None,
        authority_basis: Iterable[Mapping[str, Any]],
        bindings: AuthorityBindings,
        observed_values: Iterable[Any] = (),
        source_assertions: Iterable[str] = (),
        candidate_refs: Iterable[str] = (),
        review_decision_refs: Iterable[str] = (),
        evidence_refs: Iterable[str] = (),
        source_refs: Iterable[str] = (),
        scope: DiagnosticScope | str = DiagnosticScope.CURRENT_DIAGNOSTIC,
        constraint_result: Mapping[str, Any] | None = None,
        template_parameters: Mapping[str, Any] | None = None,
    ) -> "DiagnosticIssue":
        classification_value = DiagnosticClassification(classification)
        scope_value = DiagnosticScope(scope)
        mapping = classification_mapping(classification_value)
        severity = DiagnosticSeverity(mapping["severity"])
        template_id = mapping["template_id"]
        authority = _sort_semantic(authority_basis)
        if not authority:
            raise ValueError("every diagnostic requires an authority basis")
        for basis in authority:
            if set(basis) != {
                "requirement_type",
                "authority_iri",
                "shape_iri",
                "constraint_iri",
                "module",
                "publication_id",
            }:
                raise ValueError("diagnostic authority basis field set mismatch")
            if basis["publication_id"] != bindings.publication_id:
                raise ValueError("diagnostic authority publication mismatch")
            if not str(basis["authority_iri"]).startswith(("http://", "https://", "urn:")):
                raise ValueError("diagnostic authority must be an absolute IRI")
        parameters = {
            "focus_node": focus_node,
            "path": path,
            "authority": authority[0].get("authority_iri"),
            **dict(template_parameters or {}),
        }
        issue: dict[str, Any] = {
            "contract_version": "1.0",
            "classification": classification_value.value,
            "severity": severity.value,
            "scope": scope_value.value,
            "focus_node": focus_node,
            "path": path,
            "observed_values": _sort_semantic(observed_values),
            "authority_basis": authority,
            "source_assertions": _references(source_assertions),
            "candidate_refs": _references(candidate_refs),
            "review_decision_refs": _references(review_decision_refs),
            "evidence_refs": _references(evidence_refs),
            "source_refs": _references(source_refs),
            "publication_id": bindings.publication_id,
            "publication_semantic_hash": bindings.publication_semantic_hash,
            "repository_semantic_hash": bindings.repository_semantic_hash,
            "phase01_attestation_hash": bindings.phase01_attestation_hash,
            "diagnostic_policy_version": POLICY_VERSION,
            "template_id": template_id,
            "template_parameters": parameters,
            "explanation": _render(template_id, parameters),
        }
        if constraint_result is not None:
            issue["constraint_result"] = deepcopy(dict(constraint_result))
        basis_hash = semantic_hash(diagnostic_semantic_basis(issue))
        issue["diagnostic_basis_hash"] = basis_hash
        issue["diagnostic_id"] = f"urn:kg-mnp:diagnostic:{basis_hash}"
        validate_diagnostic_contract("diagnostic-issue", issue)
        validate_diagnostic_identity(issue)
        return cls(issue)


build_diagnostic_issue = DiagnosticIssue.create
make_diagnostic_issue = DiagnosticIssue.create
