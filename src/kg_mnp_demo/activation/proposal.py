"""Deterministic activation and rollback proposals."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .contracts import validate_activation_contract
from .errors import ActivationError, ActivationErrorCode
from .security import (
    validate_control_plane_payload,
    validate_operator_label,
)

ACTIVATION_KINDS = frozenset(
    {
        "ACTIVATE_NEW_VERIFIED_PUBLICATION",
        "ROLLBACK_TO_PRIOR_VERIFIED_PUBLICATION",
    }
)


def proposal_identity_content(proposal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in proposal.items()
        if key not in {"activation_proposal_id", "status"}
    }


def create_activation_proposal(
    *,
    activation_kind: str,
    target: Mapping[str, Any],
    base_pointer_hash: str,
    base_generation: int,
    target_authority_binding_hash: str,
    rationale: str,
    created_by_label: str,
    explicit_human_intent: bool,
    test_only: bool,
    production_authority: bool,
) -> dict[str, Any]:
    """Create a DRAFT proposal; this performs no activation or semantic review."""

    if activation_kind not in ACTIVATION_KINDS:
        raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
    if explicit_human_intent is not True:
        raise ActivationError(
            ActivationErrorCode.HUMAN_ACTIVATION_APPROVAL_REQUIRED,
            "proposal creation requires explicit human deployment intent",
        )
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 4096:
        raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
    if isinstance(base_generation, bool) or base_generation < 0:
        raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
    required_target = {
        "publication_id",
        "publication_semantic_hash",
        "repository_id",
        "repository_semantic_hash",
        "publication_attestation_sha256",
        "lineage_source_type",
        "lineage_source_attestation_sha256",
    }
    if set(target) != required_target:
        raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
    value = {
        "contract_version": "1.0",
        "activation_kind": activation_kind,
        "target_publication_id": target["publication_id"],
        "target_publication_semantic_hash": target["publication_semantic_hash"],
        "target_repository_id": target["repository_id"],
        "target_repository_semantic_hash": target["repository_semantic_hash"],
        "target_publication_attestation_sha256": target[
            "publication_attestation_sha256"
        ],
        "target_lineage_source_type": target["lineage_source_type"],
        "target_lineage_source_attestation_sha256": target[
            "lineage_source_attestation_sha256"
        ],
        "target_authority_binding_hash": target_authority_binding_hash,
        "base_pointer_hash": base_pointer_hash,
        "base_generation": base_generation,
        "rationale": rationale.strip(),
        "created_by_label": validate_operator_label(
            created_by_label, field="created_by_label"
        ),
        "explicit_human_intent": True,
        "semantic_authority": False,
        "deployment_governance_only": True,
        "test_only": test_only,
        "production_authority": production_authority,
    }
    validate_control_plane_payload(value)
    value["activation_proposal_id"] = (
        "urn:kg-mnp:test-fixture:phase06:activation-proposal:"
        if test_only
        else "urn:kg-mnp:activation-proposal:"
    ) + semantic_hash(value)
    value["status"] = "DRAFT"
    validate_activation_contract("activation-proposal", value)
    return value
