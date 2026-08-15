"""Controlled AmendmentIntakeManifest construction and validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash
from kg_mnp_demo.modeling.identifiers import input_semantic_hash

from .contracts import validate_amendment_contract
from .errors import AmendmentError, AmendmentErrorCode
from .scope import validate_amendment_scope, validate_declared_diff


@dataclass(frozen=True, slots=True)
class AmendmentIntakeManifest:
    value: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.value)

    @property
    def intake_id(self) -> str:
        return str(self.value["intake_id"])

    @property
    def amendment_type(self) -> str:
        return str(self.value["proposal_type"])

    @classmethod
    def create(
        cls,
        *,
        base_publication_id: str,
        base_publication_semantic_hash: str,
        phase04_attestation_sha256: str,
        phase04_workspace_hash: str,
        approved_amendment_request_id: str,
        base_cleaned_data: Mapping[str, Any],
        revised_cleaned_data: Mapping[str, Any],
        declared_changed_json_pointers: Iterable[str],
        proposal_type: str,
        target_diagnostic_id: str,
        expected_semantic_effect: str,
        target_json_pointers: Iterable[str] = (),
        status: str = "VALIDATED",
    ) -> AmendmentIntakeManifest:
        actual = validate_declared_diff(
            base_cleaned_data, revised_cleaned_data, declared_changed_json_pointers
        )
        validate_amendment_scope(
            amendment_type=proposal_type,
            actual_changed_json_pointers=actual,
            declared_changed_json_pointers=declared_changed_json_pointers,
            target_json_pointers=target_json_pointers,
        )
        base_hash = input_semantic_hash(base_cleaned_data)
        revised_hash = input_semantic_hash(revised_cleaned_data)
        semantic = {
            "base_publication_id": base_publication_id,
            "base_publication_semantic_hash": base_publication_semantic_hash,
            "phase04_attestation_sha256": phase04_attestation_sha256,
            "phase04_workspace_hash": phase04_workspace_hash,
            "approved_amendment_request_id": approved_amendment_request_id,
            "base_cleaned_data_hash": base_hash,
            "revised_cleaned_data_hash": revised_hash,
            "declared_changed_json_pointers": sorted(actual),
            "proposal_type": proposal_type,
            "target_diagnostic_id": target_diagnostic_id,
            "expected_semantic_effect": expected_semantic_effect,
        }
        value = {
            "contract_version": "1.0",
            "intake_id": f"urn:kg-mnp:amendment-intake:{semantic_hash(semantic)}",
            **semantic,
            "actual_changed_json_pointers": sorted(actual),
            "target_json_pointers": sorted(set(target_json_pointers)),
            "status": status,
        }
        validate_amendment_contract("amendment-intake-manifest", value)
        return cls(value)


def validate_intake(
    manifest: Mapping[str, Any],
    *,
    base_cleaned_data: Mapping[str, Any] | None = None,
    revised_cleaned_data: Mapping[str, Any] | None = None,
    approved_request: Mapping[str, Any] | None = None,
    base_publication_id: str | None = None,
    base_publication_semantic_hash: str | None = None,
) -> dict[str, Any]:
    try:
        validate_amendment_contract("amendment-intake-manifest", manifest)
    except Exception as exc:
        raise AmendmentError(AmendmentErrorCode.INVALID_CONTRACT, str(exc)) from exc
    value = dict(manifest)
    if (
        base_publication_id is not None
        and value["base_publication_id"] != base_publication_id
    ):
        raise AmendmentError(AmendmentErrorCode.STALE_AMENDMENT_BASE)
    if (
        base_publication_semantic_hash is not None
        and value["base_publication_semantic_hash"] != base_publication_semantic_hash
    ):
        raise AmendmentError(AmendmentErrorCode.STALE_AMENDMENT_BASE)
    if approved_request is not None:
        if value["approved_amendment_request_id"] != approved_request.get(
            "amendment_request_id"
        ):
            raise AmendmentError(AmendmentErrorCode.UNAPPROVED_AMENDMENT)
        if value["proposal_type"] != approved_request.get("amendment_type"):
            raise AmendmentError(AmendmentErrorCode.REENTRY_SEMANTIC_MISMATCH)
        if approved_request.get("governance_status") != "APPROVED_FOR_FUTURE_AMENDMENT":
            raise AmendmentError(AmendmentErrorCode.UNAPPROVED_AMENDMENT)
        if approved_request.get("status") != "APPROVED_FOR_FUTURE_MODELING_AMENDMENT":
            raise AmendmentError(AmendmentErrorCode.UNAPPROVED_AMENDMENT)
    if base_cleaned_data is not None and revised_cleaned_data is not None:
        actual = validate_declared_diff(
            base_cleaned_data,
            revised_cleaned_data,
            value["declared_changed_json_pointers"],
        )
        if actual != value["actual_changed_json_pointers"]:
            raise AmendmentError(AmendmentErrorCode.UNDECLARED_INPUT_CHANGE)
        validate_amendment_scope(
            amendment_type=value["proposal_type"],
            actual_changed_json_pointers=actual,
            declared_changed_json_pointers=value["declared_changed_json_pointers"],
            target_json_pointers=value.get("target_json_pointers", []),
        )
        if semantic_hash(base_cleaned_data) != value["base_cleaned_data_hash"]:
            raise AmendmentError(AmendmentErrorCode.STALE_AMENDMENT_BASE)
        if semantic_hash(revised_cleaned_data) != value["revised_cleaned_data_hash"]:
            raise AmendmentError(AmendmentErrorCode.REENTRY_SEMANTIC_MISMATCH)
    return value


def replay_key(manifest: Mapping[str, Any]) -> str:
    """Stable idempotency key for one request/input/base tuple."""

    return semantic_hash(
        {
            "approved_amendment_request_id": manifest.get(
                "approved_amendment_request_id"
            ),
            "base_publication_id": manifest.get("base_publication_id"),
            "base_publication_semantic_hash": manifest.get(
                "base_publication_semantic_hash"
            ),
            "revised_cleaned_data_hash": manifest.get("revised_cleaned_data_hash"),
        }
    )


class ReplayGuard:
    """Small explicit ledger used by controlled runs; no publication mutation."""

    def __init__(self) -> None:
        self._seen: dict[str, str] = {}

    def check(self, manifest: Mapping[str, Any], publication_id: str) -> str:
        key = replay_key(manifest)
        prior = self._seen.get(key)
        if prior is not None:
            if prior != publication_id:
                raise AmendmentError(AmendmentErrorCode.REPLAY_DETECTED)
            raise AmendmentError(AmendmentErrorCode.REPLAY_DETECTED)
        self._seen[key] = publication_id
        return key
