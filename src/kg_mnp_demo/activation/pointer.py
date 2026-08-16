"""Deterministic CurrentPublicationPointer deployment metadata."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .contracts import validate_activation_contract
from .errors import ActivationError, ActivationErrorCode


def pointer_semantic_content(pointer: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value) for key, value in pointer.items() if key != "pointer_hash"
    }


def build_current_publication_pointer(
    *,
    registry_id: str,
    generation: int,
    target: Mapping[str, Any],
    previous_pointer_hash: str,
    test_only: bool,
) -> dict[str, Any]:
    if isinstance(generation, bool) or generation < 0:
        raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
    prefix = (
        "urn:kg-mnp:test-fixture:phase06:current-publication-pointer:"
        if test_only
        else "urn:kg-mnp:current-publication-pointer:"
    )
    value = {
        "contract_version": "1.0",
        "pointer_id": prefix + semantic_hash({"registry_id": registry_id}),
        "generation": generation,
        "active_publication_id": target["publication_id"],
        "active_publication_semantic_hash": target["publication_semantic_hash"],
        "active_repository_id": target["repository_id"],
        "active_repository_semantic_hash": target["repository_semantic_hash"],
        "active_publication_attestation_sha256": target[
            "publication_attestation_sha256"
        ],
        "lineage_source_type": target["lineage_source_type"],
        "lineage_source_attestation_sha256": target[
            "lineage_source_attestation_sha256"
        ],
        "previous_pointer_hash": previous_pointer_hash,
        "semantic_authority": False,
        "deployment_selection_metadata": True,
        "status": "ACTIVE_VERIFIED_PUBLICATION",
    }
    value["pointer_hash"] = semantic_hash(pointer_semantic_content(value))
    validate_activation_contract("current-publication-pointer", value)
    return value


def validate_current_publication_pointer(
    pointer: Mapping[str, Any],
    *,
    expected_pointer_hash: str | None = None,
) -> dict[str, Any]:
    try:
        value = deepcopy(dict(pointer))
        validate_activation_contract("current-publication-pointer", value)
        digest = semantic_hash(pointer_semantic_content(value))
        if value["pointer_hash"] != digest:
            raise ValueError("pointer hash mismatch")
        if expected_pointer_hash is not None and digest != expected_pointer_hash:
            raise ValueError("pointer differs from trusted registry state")
    except ActivationError:
        raise
    except Exception as exc:
        raise ActivationError(
            ActivationErrorCode.POINTER_TAMPERED,
            "CurrentPublicationPointer integrity verification failed",
        ) from exc
    return value
