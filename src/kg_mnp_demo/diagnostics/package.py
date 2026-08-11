"""Canonical deterministic package construction."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterator

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from .authority_binding import AuthorityBindings
from .contracts import validate_diagnostic_contract
from .issue import DiagnosticIssue, validate_diagnostic_identity
from .policy import (
    POLICY_VERSION,
    DiagnosticClassification,
    DiagnosticScope,
    DiagnosticSeverity,
)


def canonical_issue_sort_key(issue: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(issue["classification"]),
        str(issue["focus_node"]),
        str(issue.get("path") or ""),
        str(issue["diagnostic_id"]),
    )


def _coverage(value: Mapping[str, Any] | None, issues: list[dict[str, Any]]) -> dict[str, Any]:
    supplied = dict(value or {})
    result = {
        "formal_requirement_count": int(supplied.get("formal_requirement_count", 0)),
        "requirements_evaluated": int(supplied.get("requirements_evaluated", 0)),
        "shacl_constraints_evaluated": int(supplied.get("shacl_constraints_evaluated", 0)),
        "focus_nodes_evaluated": int(supplied.get("focus_nodes_evaluated", 0)),
        "confirmed_assertions_evaluated": int(supplied.get("confirmed_assertions_evaluated", 0)),
        "review_decisions_considered": int(supplied.get("review_decisions_considered", 0)),
        "evidence_requirements_evaluated": int(supplied.get("evidence_requirements_evaluated", 0)),
        "source_requirements_evaluated": int(supplied.get("source_requirements_evaluated", 0)),
        "diagnostic_classifications_exercised": sorted(
            {issue["classification"] for issue in issues}
        ),
    }
    if any(value < 0 for key, value in result.items() if key != "diagnostic_classifications_exercised"):
        raise ValueError("diagnostic coverage cannot be negative")
    return result


def _summary(issues: list[dict[str, Any]]) -> dict[str, Any]:
    classifications = Counter(issue["classification"] for issue in issues)
    severities = Counter(issue["severity"] for issue in issues)
    scopes = Counter(issue["scope"] for issue in issues)
    return {
        "issues_total": len(issues),
        "issues_by_classification": {
            classification.value: classifications[classification.value]
            for classification in DiagnosticClassification
        },
        "issues_by_severity": {
            severity.value: severities[severity.value]
            for severity in DiagnosticSeverity
        },
        "current_diagnostics": scopes[DiagnosticScope.CURRENT_DIAGNOSTIC.value],
        "historical_review_context": scopes[
            DiagnosticScope.HISTORICAL_REVIEW_CONTEXT.value
        ],
    }


def diagnostic_package_semantic_content(
    package: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "contract_version": package["contract_version"],
        "issues": deepcopy(package["issues"]),
        "summary": deepcopy(package["summary"]),
        "authority_bindings": deepcopy(package["authority_bindings"]),
        "coverage": deepcopy(package["coverage"]),
        "status": package["status"],
        "diagnostic_basis_hash": package["manifest"]["diagnostic_basis_hash"],
    }


@dataclass(frozen=True)
class DeterministicDiagnosticPackage(Mapping[str, Any]):
    value: Mapping[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.value[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.value)

    def __len__(self) -> int:
        return len(self.value)

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(dict(self.value))

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.value) + b"\n"

    @property
    def package_semantic_hash(self) -> str:
        return str(self.value["manifest"]["package_semantic_hash"])


def build_diagnostic_package(
    issues: Iterable[DiagnosticIssue | Mapping[str, Any]],
    *,
    authority_bindings: AuthorityBindings | Mapping[str, Any],
    coverage: Mapping[str, Any] | None = None,
    diagnostic_basis_hash: str | None = None,
) -> DeterministicDiagnosticPackage:
    bindings = (
        authority_bindings
        if isinstance(authority_bindings, AuthorityBindings)
        else AuthorityBindings.from_dict(authority_bindings)
    )
    normalized: list[dict[str, Any]] = []
    for issue in issues:
        value = issue.to_dict() if isinstance(issue, DiagnosticIssue) else deepcopy(dict(issue))
        validate_diagnostic_contract("diagnostic-issue", value)
        validate_diagnostic_identity(value)
        if (
            value["publication_id"] != bindings.publication_id
            or value["publication_semantic_hash"] != bindings.publication_semantic_hash
            or value["repository_semantic_hash"] != bindings.repository_semantic_hash
            or value["phase01_attestation_hash"] != bindings.phase01_attestation_hash
        ):
            raise ValueError("issue authority binding mismatch")
        normalized.append(value)
    unique: dict[str, dict[str, Any]] = {}
    for issue in normalized:
        existing = unique.get(issue["diagnostic_id"])
        if existing is not None and canonical_json_bytes(existing) != canonical_json_bytes(issue):
            raise ValueError("diagnostic identifier collision")
        unique[issue["diagnostic_id"]] = issue
    normalized = sorted(unique.values(), key=canonical_issue_sort_key)
    summary = _summary(normalized)
    package: dict[str, Any] = {
        "contract_version": "1.0",
        "issues": normalized,
        "summary": summary,
        "authority_bindings": bindings.to_dict(),
        "coverage": _coverage(coverage, normalized),
        "status": "DIAGNOSTICS_VALIDATED",
        "manifest": {
            "diagnostic_basis_hash": diagnostic_basis_hash
            or semantic_hash(
                {
                    "issues": normalized,
                    "authority_bindings": bindings.to_dict(),
                    "coverage": _coverage(coverage, normalized),
                }
            )
        },
    }
    digest = semantic_hash(diagnostic_package_semantic_content(package))
    manifest = {
        "contract_version": "1.0",
        "package_id": f"urn:kg-mnp:diagnostic-package:{digest}",
        "package_semantic_hash": digest,
        "diagnostic_policy_version": POLICY_VERSION,
        "diagnostic_policy_hash": bindings.diagnostic_policy_hash,
        "diagnostic_basis_hash": package["manifest"]["diagnostic_basis_hash"],
        "issues_total": len(normalized),
        "issue_ids": [issue["diagnostic_id"] for issue in normalized],
        "status": "DIAGNOSTICS_VALIDATED",
    }
    package = {
        "contract_version": package["contract_version"],
        "manifest": manifest,
        "issues": package["issues"],
        "summary": package["summary"],
        "authority_bindings": package["authority_bindings"],
        "coverage": package["coverage"],
        "status": package["status"],
    }
    validate_diagnostic_contract("diagnostic-manifest", manifest)
    validate_diagnostic_contract("diagnostic-package", package)
    return DeterministicDiagnosticPackage(package)


build_package = build_diagnostic_package
