"""Immutable provider requests and core-owned response envelopes."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.document_io import deterministic_json_bytes
from kg_mnp.contracts.registry import validate_contract

from ..limits import ModelingLimits
from ..security import assert_safe_json


@dataclass(frozen=True)
class ImmutableModelingProviderRequest:
    artifact_bytes: bytes
    context_bytes: bytes

    @property
    def artifact(self) -> dict[str, Any]:
        return json.loads(self.artifact_bytes)

    @property
    def context(self) -> dict[str, Any]:
        return json.loads(self.context_bytes)


def build_provider_request(
    *,
    modeling_input_bundle_id: str,
    provider_snapshot_id: str,
    capability: str,
    scope_id: str,
    baseline_snapshot_id: str,
    terminology_catalog_id: str,
    term_alignment_set_id: str,
    kg_ir_dataset_ids: list[str] | tuple[str, ...],
    evidence_record_ids: list[str] | tuple[str, ...],
    context: dict[str, Any],
    limits: ModelingLimits | None = None,
) -> ImmutableModelingProviderRequest:
    effective = limits or ModelingLimits()
    limit_subset = {
        "max_total_candidates": effective.max_total_candidates,
        "max_candidate_dependencies": effective.max_candidate_dependencies,
        "max_model_response_bytes": effective.max_model_response_bytes,
        "max_model_json_depth": effective.max_model_json_depth,
        "max_rationale_characters": effective.max_rationale_characters,
    }
    core = {
        "manifest_kind": "KG_MNP_MODELING_PROVIDER_REQUEST", "schema_version": "1.0.0",
        "modeling_input_bundle_id": modeling_input_bundle_id, "provider_snapshot_id": provider_snapshot_id,
        "capability": capability,
        "immutable_payload": {
            "scope_id": scope_id, "baseline_snapshot_id": baseline_snapshot_id,
            "terminology_catalog_id": terminology_catalog_id, "term_alignment_set_id": term_alignment_set_id,
            "kg_ir_dataset_ids": sorted(set(kg_ir_dataset_ids)),
            "evidence_record_ids": sorted(set(evidence_record_ids)),
        },
        "limits": limit_subset,
    }
    digest_value = semantic_hash(core)
    artifact = {
        **core, "request_digest": digest_value,
        "request_id": stable_urn("modeling-provider-request", {"request_digest": digest_value}),
    }
    validate_contract("modeling-provider-request", artifact)
    assert_safe_json(context)
    return ImmutableModelingProviderRequest(
        artifact_bytes=deterministic_json_bytes(artifact),
        context_bytes=deterministic_json_bytes(context),
    )


def candidate_body(**values: Any) -> dict[str, Any]:
    body = {
        "candidate_type": values.pop("candidate_type"), "subject_iri": None,
        "predicate_iri": None, "object_iri": None, "label": None, "source_field": None,
        "target_iri": None, "literal": None, "values": [], "integer_value": None,
        "conversion_policy": "NONE", "null_policy": "NONE",
    }
    body.update(values)
    return body


def candidate_draft(
    *,
    draft_ref: str,
    draft_kind: str,
    candidate_action: str,
    body: dict[str, Any],
    rationale: str,
    kg_ir_item_refs: list[str] | tuple[str, ...] = (),
    evidence_refs: list[str] | tuple[str, ...] = (),
    domain_asset_refs: list[str] | tuple[str, ...] = (),
    competency_question_refs: list[str] | tuple[str, ...] = (),
    baseline_element_refs: list[str] | tuple[str, ...] = (),
    dependency_draft_refs: list[str] | tuple[str, ...] = (),
    support_status: str = "SUPPORTED",
    score_basis: str = "deterministic provider ranking; not semantic correctness probability",
    score_basis_points: int = 0,
) -> dict[str, Any]:
    return {
        "draft_kind": draft_kind, "candidate_action": candidate_action, "body": copy.deepcopy(body),
        "kg_ir_item_refs": sorted(set(kg_ir_item_refs)), "evidence_refs": sorted(set(evidence_refs)),
        "domain_asset_refs": sorted(set(domain_asset_refs)),
        "competency_question_refs": sorted(set(competency_question_refs)),
        "baseline_element_refs": sorted(set(baseline_element_refs)),
        "dependency_draft_refs": sorted(set(dependency_draft_refs)), "draft_ref": draft_ref,
        "rationale": rationale, "support_status": support_status, "score_basis": score_basis,
        "score_basis_points": score_basis_points,
    }


def build_provider_response(
    request: ImmutableModelingProviderRequest,
    *,
    candidate_drafts: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    issues: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    artifact = request.artifact
    drafts = sorted((copy.deepcopy(item) for item in candidate_drafts), key=lambda item: item["draft_ref"])
    assert_safe_json(drafts, provider_output=True, max_bytes=artifact["limits"]["max_model_response_bytes"], max_depth=artifact["limits"]["max_model_json_depth"])
    if len(drafts) > artifact["limits"]["max_total_candidates"]:
        raise ValueError("provider response candidate limit exceeded")
    core = {
        "manifest_kind": "KG_MNP_MODELING_PROVIDER_RESPONSE", "schema_version": "1.0.0",
        "request_id": artifact["request_id"], "provider_snapshot_id": artifact["provider_snapshot_id"],
        "authority_level": "PROPOSAL_ONLY", "candidate_drafts": drafts,
        "issues": sorted(copy.deepcopy(list(issues)), key=lambda item: item["issue_id"]),
    }
    digest_value = semantic_hash(core)
    response = {
        **core, "response_digest": digest_value,
        "response_id": stable_urn("modeling-provider-response", {"response_digest": digest_value}),
    }
    validate_contract("modeling-provider-response", response)
    return response
