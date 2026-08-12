"""Explicit human ResolutionReviewDecision construction."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kg_mnp_demo.modeling.canonical_json import stable_urn

from .contracts import validate_governance_contract
from .errors import GovernanceError, GovernanceErrorCode

DECISIONS = {
    "APPROVE_FOR_AMENDMENT": ("APPROVED_FOR_AMENDMENT", "ReviewApproved"),
    "REJECT": ("REJECTED", "ReviewRejected"),
    "DEFER": ("DEFERRED", "ReviewDeferred"),
}


def build_review_decision(
    *,
    workspace_id: str,
    sequence: int,
    previous_event_hash: str,
    proposal: Mapping[str, Any],
    decision: str,
    review_note: str,
    reviewed_by_label: str,
    explicit_human_action: bool,
) -> tuple[dict[str, Any], str, str]:
    if decision not in DECISIONS:
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST, "forbidden review decision"
        )
    if explicit_human_action is not True:
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST, "explicit human action is required"
        )
    if not isinstance(review_note, str) or not review_note.strip():
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST, "human review note is required"
        )
    if not isinstance(reviewed_by_label, str) or not reviewed_by_label.strip():
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST,
            "operator-supplied reviewer label is required",
        )
    semantic = {
        "workspace_id": workspace_id,
        "sequence": sequence,
        "previous_event_hash": previous_event_hash,
        "proposal_id": proposal["proposal_id"],
        "proposal_revision": proposal["proposal_revision"],
        "decision": decision,
        "review_note": review_note,
        "reviewed_by_label": reviewed_by_label,
        "explicit_human_action": True,
    }
    value = {
        "contract_version": "1.0",
        "review_decision_id": stable_urn("resolution-review-decision", semantic),
        "proposal_id": proposal["proposal_id"],
        "proposal_revision": proposal["proposal_revision"],
        "decision": decision,
        "review_note": review_note,
        "reviewed_by_label": reviewed_by_label,
        "explicit_human_action": True,
    }
    validate_governance_contract("resolution-review-decision", value)
    target, event_type = DECISIONS[decision]
    return value, target, event_type
