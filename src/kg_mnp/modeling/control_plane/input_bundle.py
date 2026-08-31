"""Closed modeling input bundle bound to current project authorities."""

from __future__ import annotations

from typing import Any

from kg_mnp.contracts.catalog import ContractCatalog
from kg_mnp.contracts.registry import validate_contract

from .alignment import verify_alignment_set
from .artifacts import finalize_document, verify_document
from .baseline import verify_baseline_snapshot
from .errors import ModelingControlError
from .scope import verify_scope
from .scope_approval import verify_scope_approval
from .terminology import verify_terminology_catalog


def build_input_bundle(
    *,
    project_lock: dict[str, Any],
    scope: dict[str, Any],
    approval: dict[str, Any],
    question_set: dict[str, Any],
    baseline: dict[str, Any],
    terminology: dict[str, Any],
    alignments: dict[str, Any],
    kg_ir_datasets: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    review_policy_id: str,
    allowed_provider_ids: list[str] | tuple[str, ...],
    quality_gate_statuses: dict[str, str] | None = None,
    accepted_review_required_datasets: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    validate_contract("project-lock", project_lock)
    verify_scope(scope, project_lock_id=project_lock["lock_id"])
    verify_scope_approval(scope, approval)
    validate_contract("competency-question-set", question_set)
    verify_baseline_snapshot(baseline)
    verify_terminology_catalog(terminology)
    verify_alignment_set(alignments)
    catalog = ContractCatalog.load()
    if project_lock["contract_catalog_digest"] != catalog.digest:
        raise ModelingControlError("Project Lock is stale against the current Contract Catalog")
    pack_lock_ids = sorted(item["pack_lock_id"] for item in project_lock["resolved_domain_packs"])
    if pack_lock_ids != sorted(scope["domain_pack_locks"]) or pack_lock_ids != sorted(baseline["domain_pack_lock_ids"]):
        raise ModelingControlError("Domain Pack Lock binding mismatch")
    statuses = quality_gate_statuses or {}
    accepted = set(accepted_review_required_datasets)
    dataset_ids: list[str] = []
    evidence_ids: set[str] = set()
    total_items = 0
    for dataset in kg_ir_datasets:
        validate_contract("kg-ir-dataset", dataset)
        if dataset["project_lock_id"] != project_lock["lock_id"]:
            raise ModelingControlError("cross-project or stale KG-IR Dataset")
        dataset_id = dataset["dataset_id"]
        if statuses.get(dataset_id) == "FAIL":
            raise ModelingControlError("quality-gate FAIL dataset cannot enter modeling")
        if statuses.get(dataset_id) == "REVIEW_REQUIRED" and dataset_id not in accepted:
            raise ModelingControlError("REVIEW_REQUIRED dataset needs explicit human acceptance")
        declared_evidence = {item["evidence_id"] for item in dataset["evidence_records"]}
        for item in dataset["items"]:
            if not set(item["evidence_refs"]).issubset(declared_evidence):
                raise ModelingControlError("KG-IR EvidenceRecord closure is incomplete")
        dataset_ids.append(dataset_id)
        evidence_ids.update(declared_evidence)
        total_items += len(dataset["items"])
    if sorted(dataset_ids) != sorted(scope["kg_ir_dataset_ids"]):
        raise ModelingControlError("Scope and Modeling Input Bundle KG-IR sets differ")
    core = {
        "manifest_kind": "KG_MNP_MODELING_INPUT_BUNDLE", "schema_version": "1.0.0",
        "project_lock_id": project_lock["lock_id"], "contract_catalog_digest": catalog.digest,
        "domain_pack_lock_ids": pack_lock_ids, "approved_scope_id": scope["scope_id"],
        "scope_approval_id": approval["approval_id"], "competency_question_set_id": question_set["question_set_id"],
        "baseline_snapshot_id": baseline["baseline_snapshot_id"],
        "terminology_catalog_id": terminology["terminology_catalog_id"],
        "term_alignment_set_id": alignments["term_alignment_set_id"],
        "kg_ir_dataset_ids": sorted(dataset_ids), "evidence_record_ids": sorted(evidence_ids),
        "provider_policy": {"allowed_provider_ids": sorted(set(allowed_provider_ids)), "network_allowed": False, "authority_level": "PROPOSAL_ONLY"},
        "review_policy_id": review_policy_id,
        "review_required_dataset_acceptances": sorted(accepted & set(dataset_ids)),
    }
    bundle = finalize_document(core, id_field="modeling_input_bundle_id", urn_kind="modeling-input-bundle")
    validate_contract("modeling-input-bundle", bundle)
    return bundle


def verify_input_bundle(value: dict[str, Any], *, current_catalog_digest: str | None = None) -> None:
    validate_contract("modeling-input-bundle", value)
    verify_document(value, id_field="modeling_input_bundle_id", urn_kind="modeling-input-bundle")
    if value["provider_policy"]["network_allowed"]:
        raise ModelingControlError("network-enabled provider policy is not allowed in Prompt 4")
    expected = current_catalog_digest or ContractCatalog.load().digest
    if value["contract_catalog_digest"] != expected:
        raise ModelingControlError("Modeling Input Bundle is stale against Contract Catalog")
