"""Stable identifiers and self-hash projections for Stage 05 review artifacts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .canonical_json import semantic_hash, stable_urn
from .identifiers import candidate_semantic_content


def _without(value: Mapping[str, Any], *fields: str) -> dict[str, Any]:
    projected = deepcopy(dict(value))
    for field in fields:
        projected.pop(field, None)
    return projected


def review_session_id(
    *,
    proposal_id: str,
    proposal_semantic_hash: str,
    reviewer_id: str,
    started_at: str,
    review_policy_id: str,
    review_policy_version: str,
    session_label: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "proposal_id": proposal_id,
        "proposal_semantic_hash": proposal_semantic_hash,
        "reviewer_id": reviewer_id,
        "started_at": started_at,
        "review_policy_id": review_policy_id,
        "review_policy_version": review_policy_version,
    }
    if session_label is not None:
        payload["session_label"] = session_label
    return stable_urn("review-session", payload)


def review_decision_id(
    *,
    proposal_id: str,
    target_id: str,
    decision: str,
    rationale: str,
    reviewer_id: str,
    decided_at: str,
    evidence_refs: list[str] | tuple[str, ...] | None = None,
    modified_candidate: Mapping[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "proposal_id": proposal_id,
        "target_id": target_id,
        "decision": decision,
        "rationale": rationale,
        "reviewer_id": reviewer_id,
        "decided_at": decided_at,
        "evidence_refs": sorted(evidence_refs or []),
    }
    if modified_candidate is not None:
        payload["modified_candidate"] = candidate_semantic_content(modified_candidate)
    return stable_urn("review-decision", payload)


def decision_log_id(
    *,
    proposal_id: str,
    proposal_semantic_hash: str,
    reviewer_id: str,
    session_id: str,
    review_policy_version: str,
) -> str:
    return stable_urn(
        "review-decision-log",
        {
            "proposal_id": proposal_id,
            "proposal_semantic_hash": proposal_semantic_hash,
            "reviewer_id": reviewer_id,
            "session_id": session_id,
            "review_policy_version": review_policy_version,
        },
    )


def decision_log_hash(decision_log: Mapping[str, Any]) -> str:
    return semantic_hash(_without(decision_log, "log_hash"))


def confirmed_item_id(
    *,
    source_candidate_id: str,
    effective_candidate_id: str,
    confirmation_mode: str,
    semantic_content: Mapping[str, Any],
) -> str:
    return stable_urn(
        "confirmed-item",
        {
            "source_candidate_id": source_candidate_id,
            "effective_candidate_id": effective_candidate_id,
            "confirmation_mode": confirmation_mode,
            "semantic_content": dict(semantic_content),
        },
    )


def package_semantic_content(package: Mapping[str, Any]) -> dict[str, Any]:
    return _without(package, "package_id", "package_semantic_hash")


def package_semantic_hash(package: Mapping[str, Any]) -> str:
    return semantic_hash(package_semantic_content(package))


def confirmed_package_id(package_or_hash: Mapping[str, Any] | str) -> str:
    if isinstance(package_or_hash, str):
        digest = package_or_hash
    else:
        digest = package_semantic_hash(package_or_hash)
    return f"urn:kg-mnp:confirmed-modeling-package:{digest}"
