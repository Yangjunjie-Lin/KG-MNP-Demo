"""Explicit human deployment review decisions, separate from semantic review."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .contracts import validate_activation_contract
from .errors import ActivationError, ActivationErrorCode
from .security import validate_operator_label

DECISIONS = {
    "APPROVE_FOR_ACTIVATION": ("APPROVED_FOR_ACTIVATION", "ActivationReviewApproved"),
    "REJECT": ("REJECTED", "ActivationReviewRejected"),
    "DEFER": ("DEFERRED", "ActivationReviewDeferred"),
}


def build_activation_review_decision(
    *,
    proposal: Mapping[str, Any],
    decision: str,
    reviewed_by_label: str,
    review_note: str,
    explicit_human_action: bool,
) -> tuple[dict[str, Any], str, str]:
    """Build a control-plane decision; it has no semantic authority."""

    if explicit_human_action is not True:
        raise ActivationError(ActivationErrorCode.HUMAN_ACTIVATION_APPROVAL_REQUIRED)
    if decision not in DECISIONS:
        raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
    if proposal.get("status") != "SUBMITTED":
        raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
    if (
        not isinstance(review_note, str)
        or not review_note.strip()
        or len(review_note) > 4096
    ):
        raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
    target, event_type = DECISIONS[decision]
    semantic = {
        "contract_version": "1.0",
        "activation_proposal_id": proposal["activation_proposal_id"],
        "decision": decision,
        "resulting_status": target,
        "reviewed_by_label": validate_operator_label(
            reviewed_by_label, field="reviewed_by_label"
        ),
        "review_note": review_note.strip(),
        "explicit_human_action": True,
        "operator_identity_claim": "OPERATOR_SUPPLIED_LABEL_ONLY",
        "semantic_authority": False,
        "deployment_governance_only": True,
        "test_only": proposal["test_only"],
        "production_authority": proposal["production_authority"],
    }
    semantic["activation_review_decision_id"] = (
        "urn:kg-mnp:test-fixture:phase06:activation-review-decision:"
        if proposal["test_only"]
        else "urn:kg-mnp:activation-review-decision:"
    ) + semantic_hash(semantic)
    validate_activation_contract("activation-review-decision", semantic)
    return semantic, target, event_type
