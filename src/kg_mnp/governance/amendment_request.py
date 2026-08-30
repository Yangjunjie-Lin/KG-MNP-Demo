"""Non-patch ApprovedAmendmentRequest construction."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .contracts import validate_governance_contract
from .errors import GovernanceError, GovernanceErrorCode
from .identity import governance_urn


def build_approved_amendment_request(
    *,
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    review_event_id: str,
) -> dict[str, Any]:
    if decision.get("decision") != "APPROVE_FOR_AMENDMENT":
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST, "approval decision required"
        )
    semantic = {
        "proposal_id": proposal["proposal_id"],
        "review_decision_id": decision["review_decision_id"],
        "target_diagnostic_id": proposal["target_diagnostic_id"],
        "authority_type": proposal["authority_type"],
        "publication_id": proposal["publication_id"],
        "publication_semantic_hash": proposal["publication_semantic_hash"],
        "repository_semantic_hash": proposal["repository_semantic_hash"],
        "upstream_phase03_attestation_sha256": proposal[
            "upstream_phase03_attestation_sha256"
        ],
        "upstream_phase03_diagnostic_package_hash": proposal[
            "upstream_phase03_diagnostic_package_hash"
        ],
        "amendment_type": proposal["proposal_type"],
        "structured_proposed_payload": proposal["proposed_payload"],
        "provenance_chain": [
            proposal["target_diagnostic_id"],
            proposal["proposal_id"],
            decision["review_decision_id"],
            review_event_id,
        ],
    }
    value = {
        "contract_version": "1.0",
        "amendment_request_id": governance_urn(
            "approved-amendment-request", semantic, str(proposal["authority_type"])
        ),
        **deepcopy(semantic),
        "governance_status": "APPROVED_FOR_FUTURE_AMENDMENT",
        "status": "APPROVED_FOR_FUTURE_MODELING_AMENDMENT",
    }
    validate_governance_contract("approved-amendment-request", value)
    return value
