"""Thin bridge to the existing Stage 05 human review engine."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kg_mnp_demo.modeling.confirmation import build_confirmed_modeling_package
from kg_mnp_demo.modeling.review_log import (
    finalize_review_decision_log,
    init_review_decision_log,
    record_review_action,
)
from kg_mnp_demo.modeling.semantic_validation import (
    validate_confirmed_modeling_package_semantics,
)

from .errors import AmendmentError, AmendmentErrorCode


def start_review_session(
    proposal: Mapping[str, Any],
    *,
    reviewer_id: str,
    display_name: str,
    role: str,
    started_at: str,
    session_id: str | None = None,
    affiliation: str | None = None,
) -> dict[str, Any]:
    return init_review_decision_log(
        proposal,
        reviewer_id=reviewer_id,
        display_name=display_name,
        role=role,
        started_at=started_at,
        session_label=session_id,
        affiliation=affiliation,
    )


def record_human_review(
    proposal: Mapping[str, Any],
    draft_log: Mapping[str, Any],
    action: Mapping[str, Any],
    *,
    review_policy: Mapping[str, Any] | None = None,
    term_types: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if action.get("explicit_human_action") is False:
        raise AmendmentError(AmendmentErrorCode.AUTO_CONFIRM_BLOCKED)
    return record_review_action(
        proposal,
        draft_log,
        action,
        review_policy=review_policy,
        term_types=term_types,
    )


def finalize_human_review(
    proposal: Mapping[str, Any],
    draft_log: Mapping[str, Any],
    *,
    completed_at: str,
    cleaned_partial_data: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    review_policy: Mapping[str, Any] | None = None,
    term_types: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return finalize_review_decision_log(
        proposal,
        draft_log,
        completed_at=completed_at,
        cleaned_partial_data=cleaned_partial_data,
        ontology_baseline=ontology_baseline,
        mapping_rules=mapping_rules,
        review_policy=review_policy,
        term_types=term_types,
    )


def build_and_validate_confirmed_package(
    *,
    cleaned_partial_data: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    terminology_profile: Mapping[str, Any],
    proposal_policy: Mapping[str, Any],
    review_policy: Mapping[str, Any],
    term_types: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    package = build_confirmed_modeling_package(
        cleaned_partial_data,
        proposal,
        decision_log,
        ontology_baseline,
        mapping_rules,
        terminology_profile,
        proposal_policy,
        review_policy,
        term_types=term_types,
    )
    # Independent Stage 05 reconstruction is retained as an explicit gate.
    validate_confirmed_modeling_package_semantics(
        package,
        proposal,
        decision_log,
        cleaned_partial_data=cleaned_partial_data,
        ontology_baseline=ontology_baseline,
        mapping_rules=mapping_rules,
        terminology_profile=terminology_profile,
        proposal_policy=proposal_policy,
        review_policy=review_policy,
        term_types=term_types,
        require_complete=True,
    )
    return package


def require_explicit_review(decision_log: Mapping[str, Any]) -> None:
    decisions = decision_log.get("decisions")
    session = decision_log.get("review_session") or {}
    if not isinstance(decisions, list) or not session.get("completed_at"):
        raise AmendmentError(
            AmendmentErrorCode.AUTO_CONFIRM_BLOCKED,
            "Phase05 cannot synthesize or append a semantic confirmation",
        )
