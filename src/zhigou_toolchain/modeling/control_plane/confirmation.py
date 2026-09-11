"""Deterministic, compiler-ready modeling package without RDF or publication authority."""

from __future__ import annotations

from typing import Any

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.contracts.catalog import ContractCatalog
from zhigou_toolchain.contracts.registry import validate_contract

from .artifacts import finalize_document, verify_document
from .errors import ConfirmedPackageError
from .input_bundle import verify_input_bundle
from .prevalidation import verify_prevalidation
from .proposal import verify_proposal
from .review.finalization import FinalizationResult
from .review.log import verify_decision_log
from .security import assert_confirmed_package_safe


def build_confirmed_package(
    *,
    project_lock: dict[str, Any],
    input_bundle: dict[str, Any],
    scope: dict[str, Any],
    scope_approval: dict[str, Any],
    question_set: dict[str, Any],
    coverage_report: dict[str, Any],
    baseline: dict[str, Any],
    terminology: dict[str, Any],
    alignments: dict[str, Any],
    field_mappings: dict[str, Any],
    proposal: dict[str, Any],
    prevalidation: dict[str, Any],
    review_policy: dict[str, Any],
    finalization: FinalizationResult,
    actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    review_queue: dict[str, Any],
    minimum_compiler_version: str = "0.5.0",
) -> dict[str, Any]:
    catalog = ContractCatalog.load()
    validate_contract("project-lock", project_lock)
    verify_input_bundle(input_bundle, current_catalog_digest=catalog.digest)
    verify_proposal(proposal)
    verify_prevalidation(prevalidation, proposal=proposal)
    verify_decision_log(
        finalization.decision_log,
        queue=review_queue,
        proposal=proposal,
        prevalidation=prevalidation,
        policy=review_policy,
        actions=actions,
    )
    if project_lock["lock_id"] != input_bundle["project_lock_id"]:
        raise ConfirmedPackageError("confirmed package authorities use different Project Locks")
    authority_pairs = (
        (input_bundle["approved_scope_id"], scope["scope_id"]),
        (input_bundle["scope_approval_id"], scope_approval["approval_id"]),
        (input_bundle["competency_question_set_id"], question_set["question_set_id"]),
        (input_bundle["baseline_snapshot_id"], baseline["baseline_snapshot_id"]),
        (input_bundle["terminology_catalog_id"], terminology["terminology_catalog_id"]),
        (input_bundle["term_alignment_set_id"], alignments["term_alignment_set_id"]),
    )
    if any(expected != actual for expected, actual in authority_pairs):
        raise ConfirmedPackageError("confirmed package authority closure mismatch")
    accepted = [
        *finalization.accepted_tbox,
        *finalization.accepted_mapping,
        *finalization.accepted_abox,
        *finalization.accepted_shacl,
    ]
    evidence_refs = sorted({ref for candidate in accepted for ref in candidate["evidence_refs"]})
    dependency_refs = sorted(
        {ref for candidate in accepted for ref in candidate["dependency_candidate_refs"]}
    )
    artifact_ids = sorted(
        {
            project_lock["lock_id"],
            *input_bundle["domain_pack_lock_ids"],
            scope["scope_id"],
            scope_approval["approval_id"],
            question_set["question_set_id"],
            coverage_report["coverage_report_id"],
            *input_bundle["kg_ir_dataset_ids"],
            *input_bundle["evidence_record_ids"],
            baseline["baseline_snapshot_id"],
            terminology["terminology_catalog_id"],
            alignments["term_alignment_set_id"],
            field_mappings["field_mapping_candidate_set_id"],
            proposal["proposal_id"],
            prevalidation["formal_prevalidation_report_id"],
            review_policy["policy_id"],
            finalization.decision_log["review_decision_log_id"],
            *proposal["provider_snapshots"],
            *proposal["model_invocation_records"],
            *evidence_refs,
        }
    )
    core = {
        "manifest_kind": "KG_MNP_ONTOLOGY_CONFIRMED_MODELING_PACKAGE",
        "schema_version": "1.0.0",
        "package_status": "READY_FOR_COMPILATION",
        "project_lock_id": project_lock["lock_id"],
        "contract_catalog_digest": catalog.digest,
        "domain_pack_lock_ids": input_bundle["domain_pack_lock_ids"],
        "scope_id": scope["scope_id"],
        "scope_approval_id": scope_approval["approval_id"],
        "competency_question_set_id": question_set["question_set_id"],
        "competency_question_coverage_report_id": coverage_report["coverage_report_id"],
        "kg_ir_dataset_ids": input_bundle["kg_ir_dataset_ids"],
        "baseline_snapshot_id": baseline["baseline_snapshot_id"],
        "terminology_catalog_id": terminology["terminology_catalog_id"],
        "term_alignment_set_id": alignments["term_alignment_set_id"],
        "field_mapping_candidate_set_id": field_mappings[
            "field_mapping_candidate_set_id"
        ],
        "source_proposal_id": proposal["proposal_id"],
        "source_proposal_digest": proposal["content_digest"],
        "formal_prevalidation_report_id": prevalidation[
            "formal_prevalidation_report_id"
        ],
        "review_policy_id": review_policy["policy_id"],
        "review_decision_log_id": finalization.decision_log[
            "review_decision_log_id"
        ],
        "review_semantic_hash": finalization.decision_log["semantic_decision_hash"],
        "confirmed_tbox": list(finalization.accepted_tbox),
        "confirmed_mapping": list(finalization.accepted_mapping),
        "confirmed_abox": list(finalization.accepted_abox),
        "confirmed_shacl": list(finalization.accepted_shacl),
        "rejected_candidates": list(finalization.rejected_candidate_ids),
        "deferred_candidates": list(finalization.deferred_candidate_ids),
        "resolved_conflicts": list(finalization.resolved_conflict_ids),
        "evidence_closure": {
            "required_count": len(evidence_refs),
            "closed_count": len(evidence_refs),
            "coverage_basis_points": 10000,
        },
        "dependency_closure": {
            "required_count": len(dependency_refs),
            "closed_count": len(dependency_refs),
            "coverage_basis_points": 10000,
        },
        "compiler_requirements": {
            "input_contract": "ontology-confirmed-modeling-package/1.0.0",
            "minimum_compiler_version": minimum_compiler_version,
            "required_validation_profiles": [
                "OWL_FINAL_CONSISTENCY",
                "SHACL_FINAL_VALIDATION",
                "CQ_EXECUTION",
                "PROVENANCE_CLOSURE",
            ],
        },
        "artifact_manifest": {
            "artifact_ids": artifact_ids,
            "artifact_sha256": semantic_hash({"artifact_ids": artifact_ids}),
        },
    }
    assert_confirmed_package_safe(core)
    package = finalize_document(
        core,
        id_field="package_id",
        urn_kind="ontology-confirmed-modeling-package",
    )
    validate_contract("ontology-confirmed-modeling-package", package)
    return package


def verify_confirmed_package(package: dict[str, Any]) -> None:
    validate_contract("ontology-confirmed-modeling-package", package)
    assert_confirmed_package_safe(package)
    verify_document(
        package,
        id_field="package_id",
        urn_kind="ontology-confirmed-modeling-package",
    )
    if package["package_status"] != "READY_FOR_COMPILATION":
        raise ConfirmedPackageError("confirmed package has an unauthorized status")
    artifact_ids = package["artifact_manifest"]["artifact_ids"]
    expected = semantic_hash({"artifact_ids": artifact_ids})
    if expected != package["artifact_manifest"]["artifact_sha256"]:
        raise ConfirmedPackageError("confirmed package Artifact Manifest is tampered")
    for partition_name, expected_scope in (
        ("confirmed_tbox", "TBOX"),
        ("confirmed_mapping", "MAPPING"),
        ("confirmed_abox", "ABOX"),
        ("confirmed_shacl", "SHACL"),
    ):
        if any(item["publication_scope"] != expected_scope for item in package[partition_name]):
            raise ConfirmedPackageError("confirmed candidate partition is invalid")
