"""Stable identifiers and self-hash projections for modeling contracts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .canonical_json import semantic_hash, stable_urn


def _without(value: Mapping[str, Any], *fields: str) -> dict[str, Any]:
    projected = deepcopy(dict(value))
    for field in fields:
        projected.pop(field, None)
    return projected


def input_semantic_hash(cleaned_partial_data: Mapping[str, Any]) -> str:
    return semantic_hash(cleaned_partial_data)


def input_id(cleaned_partial_data: Mapping[str, Any]) -> str:
    return f"urn:kg-mnp:input:{input_semantic_hash(cleaned_partial_data)}"


def candidate_semantic_content(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return _without(candidate, "candidate_id")


def candidate_id(candidate: Mapping[str, Any]) -> str:
    return stable_urn("candidate", candidate_semantic_content(candidate))


def issue_semantic_content(issue: Mapping[str, Any]) -> dict[str, Any]:
    return _without(issue, "issue_id")


def issue_id(issue: Mapping[str, Any]) -> str:
    return stable_urn("issue", issue_semantic_content(issue))


def proposal_semantic_content(proposal: Mapping[str, Any]) -> dict[str, Any]:
    return _without(proposal, "proposal_id", "proposal_semantic_hash")


def proposal_semantic_hash(proposal: Mapping[str, Any]) -> str:
    return semantic_hash(proposal_semantic_content(proposal))


def proposal_id(proposal: Mapping[str, Any]) -> str:
    return f"urn:kg-mnp:modeling-proposal:{proposal_semantic_hash(proposal)}"


def dependency_reference(kind: str, value: Mapping[str, Any]) -> dict[str, str]:
    """Return an auditable reference for an immutable dependency payload."""

    digest = semantic_hash(value)
    return {
        "dependency_id": stable_urn("dependency", {"kind": kind, "hash": digest}),
        "dependency_kind": kind,
        "semantic_hash": digest,
    }

