"""Governance lineage kept separate from business/source evidence."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .errors import AmendmentError, AmendmentErrorCode

FIELDS = {
    "base_publication_id",
    "target_diagnostic_id",
    "phase04_proposal_id",
    "phase04_review_decision_id",
    "approved_amendment_request_id",
    "amendment_intake_id",
    "revised_cleaned_data_hash",
    "modeling_proposal_id",
    "modeling_candidate_id",
    "review_decision_log_id",
    "review_decision_id",
    "confirmed_modeling_package_id",
    "confirmed_item_id",
    "new_publication_id",
    "governance_lineage_hash",
}


def build_amendment_lineage(
    *,
    amendment_request: Mapping[str, Any],
    intake_manifest: Mapping[str, Any],
    modeling_proposal: Mapping[str, Any],
    modeling_candidate: Mapping[str, Any],
    review_decision_log: Mapping[str, Any],
    review_decision: Mapping[str, Any],
    confirmed_modeling_package: Mapping[str, Any],
    confirmed_item: Mapping[str, Any],
    new_publication_id: str,
) -> dict[str, Any]:
    semantic = {
        "base_publication_id": amendment_request["publication_id"],
        "target_diagnostic_id": amendment_request["target_diagnostic_id"],
        "phase04_proposal_id": amendment_request["proposal_id"],
        "phase04_review_decision_id": amendment_request["review_decision_id"],
        "approved_amendment_request_id": amendment_request["amendment_request_id"],
        "amendment_intake_id": intake_manifest["intake_id"],
        "revised_cleaned_data_hash": intake_manifest["revised_cleaned_data_hash"],
        "modeling_proposal_id": modeling_proposal["proposal_id"],
        "modeling_candidate_id": modeling_candidate["candidate_id"],
        "review_decision_log_id": review_decision_log["decision_log_id"],
        "review_decision_id": review_decision["decision_id"],
        "confirmed_modeling_package_id": confirmed_modeling_package["package_id"],
        "confirmed_item_id": confirmed_item["confirmed_candidate"]["confirmed_item_id"],
        "new_publication_id": new_publication_id,
    }
    value = {**semantic, "governance_lineage_hash": semantic_hash(semantic)}
    validate_amendment_lineage(
        value,
        amendment_request=amendment_request,
        intake_manifest=intake_manifest,
    )
    return value


def validate_amendment_lineage(
    lineage: Mapping[str, Any],
    *,
    amendment_request: Mapping[str, Any],
    intake_manifest: Mapping[str, Any],
) -> None:
    if set(lineage) != FIELDS:
        raise AmendmentError(
            AmendmentErrorCode.AUTHORITY_MISMATCH, "lineage field set mismatch"
        )
    semantic = {
        key: deepcopy(lineage[key]) for key in FIELDS - {"governance_lineage_hash"}
    }
    expected = (
        (lineage["base_publication_id"], amendment_request.get("publication_id")),
        (
            lineage["target_diagnostic_id"],
            amendment_request.get("target_diagnostic_id"),
        ),
        (lineage["phase04_proposal_id"], amendment_request.get("proposal_id")),
        (
            lineage["phase04_review_decision_id"],
            amendment_request.get("review_decision_id"),
        ),
        (
            lineage["approved_amendment_request_id"],
            amendment_request.get("amendment_request_id"),
        ),
        (lineage["amendment_intake_id"], intake_manifest.get("intake_id")),
        (
            lineage["revised_cleaned_data_hash"],
            intake_manifest.get("revised_cleaned_data_hash"),
        ),
        (lineage["governance_lineage_hash"], semantic_hash(semantic)),
    )
    if any(left != right for left, right in expected):
        raise AmendmentError(
            AmendmentErrorCode.AUTHORITY_MISMATCH, "amendment lineage mismatch"
        )
