"""Reconstruct Prompt 4 authority closure before compilation."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn
from zhigou_toolchain.contracts.catalog import ContractCatalog, verify_catalog_lock
from zhigou_toolchain.contracts.registry import validate_contract
from zhigou_toolchain.domain_packs.registry import DomainPackRegistry
from zhigou_toolchain.ingestion.contracts import verify_finalized_document
from zhigou_toolchain.ingestion.source_store import SourceStore
from zhigou_toolchain.modeling.control_plane.alignment import verify_alignment_set
from zhigou_toolchain.modeling.control_plane.artifacts import verify_document
from zhigou_toolchain.modeling.control_plane.baseline import verify_baseline_snapshot
from zhigou_toolchain.modeling.control_plane.competency import verify_question_set
from zhigou_toolchain.modeling.control_plane.confirmation import (
    verify_confirmed_package,
)
from zhigou_toolchain.modeling.control_plane.mappings import verify_field_mapping_set
from zhigou_toolchain.modeling.control_plane.prevalidation import verify_prevalidation
from zhigou_toolchain.modeling.control_plane.proposal import verify_proposal
from zhigou_toolchain.modeling.control_plane.review.policy import verify_review_policy
from zhigou_toolchain.modeling.control_plane.scope import verify_scope
from zhigou_toolchain.modeling.control_plane.scope_approval import verify_scope_approval
from zhigou_toolchain.modeling.control_plane.terminology import (
    verify_terminology_catalog,
)
from zhigou_toolchain.workspace.locking import verify_project_lock
from zhigou_toolchain.workspace.service import load_project_manifest

from .artifact_resolver import ResolvedArtifact, WorkspaceArtifactResolver
from .contracts import finalize_artifact
from .errors import InputAttestationError
from .validation import validate_confirmed_candidates

_AUTHORITY_FIELDS = (
    "project_lock_id",
    "scope_id",
    "scope_approval_id",
    "competency_question_set_id",
    "competency_question_coverage_report_id",
    "baseline_snapshot_id",
    "terminology_catalog_id",
    "term_alignment_set_id",
    "field_mapping_candidate_set_id",
    "source_proposal_id",
    "formal_prevalidation_report_id",
    "review_policy_id",
    "review_decision_log_id",
)

_KIND_TO_CONTRACT = {
    "KG_MNP_PROJECT_LOCK": "project-lock",
    "KG_MNP_ONTOLOGY_SCOPE": "ontology-scope",
    "KG_MNP_ONTOLOGY_SCOPE_APPROVAL": "ontology-scope-approval",
    "KG_MNP_COMPETENCY_QUESTION_SET": "competency-question-set",
    "KG_MNP_COMPETENCY_QUESTION_COVERAGE_REPORT": "competency-question-coverage-report",
    "KG_MNP_KG_IR_DATASET": "kg-ir-dataset",
    "KG_MNP_ONTOLOGY_BASELINE_SNAPSHOT": "ontology-baseline-snapshot",
    "KG_MNP_TERMINOLOGY_CATALOG": "terminology-catalog",
    "KG_MNP_TERM_ALIGNMENT_SET": "term-alignment-set",
    "KG_MNP_FIELD_MAPPING_CANDIDATE_SET": "field-mapping-candidate-set",
    "KG_MNP_ONTOLOGY_MODELING_PROPOSAL": "ontology-modeling-proposal",
    "KG_MNP_FORMAL_PREVALIDATION_REPORT": "formal-prevalidation-report",
    "KG_MNP_ONTOLOGY_REVIEW_POLICY": "ontology-review-policy",
    "KG_MNP_ONTOLOGY_REVIEW_DECISION_LOG": "ontology-review-decision-log",
    "KG_MNP_PLUGIN_SNAPSHOT": "plugin-snapshot",
    "KG_MNP_EVIDENCE_RECORD": "evidence-record",
}


def _validate_resolved(record: ResolvedArtifact) -> None:
    contract = _KIND_TO_CONTRACT.get(record.document.get("manifest_kind"))
    if contract == "plugin-snapshot" and record.document.get("schema_version") == "1.1.0":
        contract = "plugin-snapshot-v1-1"
    if contract is not None:
        validate_contract(contract, record.document)


def _verify_review_log(log: dict[str, Any]) -> None:
    validate_contract("ontology-review-decision-log", log)
    core = copy.deepcopy(log)
    actual_id = core.pop("review_decision_log_id")
    actual_digest = core.pop("content_digest")
    if actual_digest != semantic_hash(core):
        raise InputAttestationError("review decision log content digest mismatch")
    expected_id = stable_urn(
        "ontology-review-decision-log",
        {"semantic_decision_hash": log["semantic_decision_hash"]},
    )
    if actual_id != expected_id:
        raise InputAttestationError("review decision log ID does not bind its semantic hash")


def _verify_kgir_dataset(dataset: dict[str, Any], *, project_lock_id: str) -> None:
    verify_finalized_document(
        dataset,
        contract="kg-ir-dataset",
        id_field="dataset_id",
        urn_kind="kg-ir-dataset",
    )
    if dataset["project_lock_id"] != project_lock_id:
        raise InputAttestationError("cross-project or stale KG-IR Dataset")
    for item in dataset["items"]:
        verify_finalized_document(
            item,
            contract="kg-ir-item",
            id_field="item_id",
            urn_kind="kg-ir-item",
        )
    for evidence in dataset["evidence_records"]:
        verify_finalized_document(
            evidence,
            contract="evidence-record",
            id_field="evidence_id",
            urn_kind="evidence",
        )
    for transformation in dataset["transformation_records"]:
        verify_finalized_document(
            transformation,
            contract="transformation-record",
            id_field="transformation_id",
            urn_kind="transformation",
        )
    for snapshot in dataset["plugin_snapshots"]:
        contract = "plugin-snapshot-v1-1" if snapshot["schema_version"] == "1.1.0" else "plugin-snapshot"
        validate_contract(contract, snapshot)
        preimage = dict(snapshot)
        actual = preimage.pop("snapshot_id")
        if actual != stable_urn("plugin-snapshot", preimage):
            raise InputAttestationError("Plugin Snapshot identity mismatch")


def _verify_authority_closure(
    confirmed_package: dict[str, Any],
    records: dict[str, ResolvedArtifact],
) -> None:
    project_lock_id = confirmed_package["project_lock_id"]
    for record in records.values():
        bound_lock = record.document.get("project_lock_id")
        if isinstance(bound_lock, str) and bound_lock != project_lock_id:
            raise InputAttestationError("cross-project authority reference")
    scope = records[confirmed_package["scope_id"]].document
    approval = records[confirmed_package["scope_approval_id"]].document
    questions = records[confirmed_package["competency_question_set_id"]].document
    coverage = records[confirmed_package["competency_question_coverage_report_id"]].document
    baseline = records[confirmed_package["baseline_snapshot_id"]].document
    terminology = records[confirmed_package["terminology_catalog_id"]].document
    alignments = records[confirmed_package["term_alignment_set_id"]].document
    mappings = records[confirmed_package["field_mapping_candidate_set_id"]].document
    proposal = records[confirmed_package["source_proposal_id"]].document
    prevalidation = records[confirmed_package["formal_prevalidation_report_id"]].document
    review_policy = records[confirmed_package["review_policy_id"]].document
    review = records[confirmed_package["review_decision_log_id"]].document

    verify_scope(scope, project_lock_id=project_lock_id)
    verify_scope_approval(scope, approval)
    verify_question_set(questions)
    verify_document(coverage, id_field="coverage_report_id", urn_kind="competency-question-coverage-report")
    verify_baseline_snapshot(baseline)
    verify_terminology_catalog(terminology)
    verify_alignment_set(alignments)
    verify_field_mapping_set(mappings)
    verify_proposal(proposal)
    verify_prevalidation(prevalidation, proposal=proposal)
    verify_review_policy(review_policy, project_lock_id=project_lock_id)
    _verify_review_log(review)

    if questions["project_lock_id"] != project_lock_id or questions["scope_id"] != scope["scope_id"]:
        raise InputAttestationError("competency question authority closure mismatch")
    if coverage["question_set_id"] != questions["question_set_id"] or coverage["proposal_id"] != proposal["proposal_id"] or coverage["execution_claimed"] is not False:
        raise InputAttestationError("competency question coverage report is stale or overclaims execution")
    if review["proposal_id"] != proposal["proposal_id"] or review["prevalidation_report_id"] != prevalidation["formal_prevalidation_report_id"] or review["review_policy_id"] != review_policy["policy_id"]:
        raise InputAttestationError("review decision authority closure mismatch")

    kgir_items: set[str] = set()
    evidence_ids: set[str] = set()
    provider_snapshot_ids: set[str] = set()
    transformation_ids: set[str] = set()
    for dataset_id in confirmed_package["kg_ir_dataset_ids"]:
        dataset = records[dataset_id].document
        _verify_kgir_dataset(dataset, project_lock_id=project_lock_id)
        kgir_items.update(item["item_id"] for item in dataset["items"])
        evidence_ids.update(item["evidence_id"] for item in dataset["evidence_records"])
        provider_snapshot_ids.update(item["snapshot_id"] for item in dataset["plugin_snapshots"])
        transformation_ids.update(item["transformation_id"] for item in dataset["transformation_records"])
        for evidence in dataset["evidence_records"]:
            if evidence["plugin_snapshot_id"] not in provider_snapshot_ids:
                raise InputAttestationError("EvidenceRecord Plugin Snapshot closure is incomplete")
            if not set(evidence["transformation_ids"]).issubset(transformation_ids):
                raise InputAttestationError("EvidenceRecord transformation closure is incomplete")
    confirmed_candidates = [
        *confirmed_package["confirmed_tbox"],
        *confirmed_package["confirmed_mapping"],
        *confirmed_package["confirmed_abox"],
        *confirmed_package["confirmed_shacl"],
    ]
    candidate_ids = {item["candidate_id"] for item in confirmed_candidates}
    all_provider_ids = set(proposal["provider_snapshots"])
    for candidate in confirmed_candidates:
        if not set(candidate["kg_ir_item_refs"]).issubset(kgir_items):
            raise InputAttestationError("confirmed Candidate KG-IR closure is incomplete")
        if not set(candidate["evidence_refs"]).issubset(evidence_ids):
            raise InputAttestationError("confirmed Candidate evidence closure is incomplete")
        if not set(candidate["provider_snapshot_refs"]).issubset(all_provider_ids):
            raise InputAttestationError("confirmed Candidate Provider Snapshot closure is incomplete")
        if not set(candidate["dependency_candidate_refs"]).issubset(candidate_ids):
            raise InputAttestationError("confirmed Candidate dependency closure is incomplete")

    decisions = review["final_decisions"]
    proposal_ids = {
        item["candidate_id"]
        for name in ("tbox_candidates", "mapping_candidates", "abox_candidates", "shacl_candidates")
        for item in proposal[name]
    }
    if {item["candidate_id"] for item in decisions} != proposal_ids:
        raise InputAttestationError("review decision log does not cover every proposed Candidate")
    accepted_ids = {
        item["effective_candidate_id"]
        for item in decisions
        if item["decision"] in {"ACCEPT", "MODIFY_AND_ACCEPT", "REUSE_EXISTING"}
    }
    if accepted_ids != candidate_ids:
        raise InputAttestationError("confirmed partitions differ from positive review decisions")
    blocking = {item["issue_id"] for item in proposal["conflicts"] if item["severity"] == "BLOCKING"}
    if not blocking.issubset(set(confirmed_package["resolved_conflicts"])):
        raise InputAttestationError("unresolved blocking modeling conflict")

    evidence_refs = {ref for candidate in confirmed_candidates for ref in candidate["evidence_refs"]}
    dependency_refs = {ref for candidate in confirmed_candidates for ref in candidate["dependency_candidate_refs"]}
    expected_evidence = {
        "required_count": len(evidence_refs),
        "closed_count": len(evidence_refs & evidence_ids),
        "coverage_basis_points": 10000 if not evidence_refs else len(evidence_refs & evidence_ids) * 10000 // len(evidence_refs),
    }
    expected_dependencies = {
        "required_count": len(dependency_refs),
        "closed_count": len(dependency_refs & candidate_ids),
        "coverage_basis_points": 10000 if not dependency_refs else len(dependency_refs & candidate_ids) * 10000 // len(dependency_refs),
    }
    if confirmed_package["evidence_closure"] != expected_evidence or confirmed_package["dependency_closure"] != expected_dependencies:
        raise InputAttestationError("confirmed package closure claims do not match reconstructed closure")


def attest_compiler_input(
    workspace: Path | str,
    confirmed_package: dict[str, Any],
    *,
    confirmed_bytes: bytes | None = None,
    supported_types: set[str],
    domain_packs_root: Path | str,
) -> dict[str, Any]:
    verify_catalog_lock()
    try:
        verify_confirmed_package(confirmed_package)
    except Exception as exc:
        raise InputAttestationError(f"confirmed package verification failed: {exc}") from exc
    catalog = ContractCatalog.load()
    if confirmed_package["contract_catalog_digest"] != catalog.digest:
        raise InputAttestationError("confirmed package is stale for the current Contract Catalog", code="STALE_CATALOG")
    if confirmed_package["compiler_requirements"]["input_contract"] != "ontology-confirmed-modeling-package/1.0.0":
        raise InputAttestationError("wrong compiler input profile")
    partitions = {
        "TBOX": confirmed_package["confirmed_tbox"],
        "MAPPING": confirmed_package["confirmed_mapping"],
        "ABOX": confirmed_package["confirmed_abox"],
        "SHACL": confirmed_package["confirmed_shacl"],
    }
    validate_confirmed_candidates(partitions, supported_types=supported_types)
    workspace_root = Path(workspace).resolve(strict=True)
    resolver = WorkspaceArtifactResolver(workspace_root)
    required_ids = [confirmed_package[field] for field in _AUTHORITY_FIELDS]
    required_ids.extend(confirmed_package["kg_ir_dataset_ids"])
    required_ids.extend(confirmed_package["domain_pack_lock_ids"])
    required_ids.extend(confirmed_package["artifact_manifest"]["artifact_ids"])
    records: dict[str, ResolvedArtifact] = {}
    missing_domain_locks = set(confirmed_package["domain_pack_lock_ids"])
    for artifact_id in sorted(set(required_ids)):
        try:
            record = resolver.resolve(artifact_id)
        except InputAttestationError:
            if artifact_id in missing_domain_locks:
                continue
            raise
        _validate_resolved(record)
        records[artifact_id] = record
    complete_index = resolver.index
    for dataset_id in confirmed_package["kg_ir_dataset_ids"]:
        dataset = records[dataset_id].document
        closure_ids = {
            *(item["item_id"] for item in dataset["items"]),
            *(item["evidence_id"] for item in dataset["evidence_records"]),
            *(item["transformation_id"] for item in dataset["transformation_records"]),
            *(item["snapshot_id"] for item in dataset["plugin_snapshots"]),
            *(item["source_id"] for item in dataset["evidence_records"]),
        }
        for artifact_id in sorted(closure_ids):
            record = complete_index.get(artifact_id)
            if record is None:
                raise InputAttestationError(
                    f"KG-IR authority closure is missing: {artifact_id}"
                )
            _validate_resolved(record)
            records[artifact_id] = record
    registry = DomainPackRegistry(domain_packs_root)
    verified_project_lock = verify_project_lock(load_project_manifest(workspace_root), registry)
    project_lock = records[confirmed_package["project_lock_id"]].document
    if project_lock != verified_project_lock.document:
        raise InputAttestationError("Project Lock is tampered or not the current workspace lock", code="STALE_PROJECT_LOCK")
    if project_lock.get("contract_catalog_digest") != catalog.digest:
        raise InputAttestationError("Project Lock is stale for the current Catalog", code="STALE_PROJECT_LOCK")
    resolved_lock_ids = {item["pack_lock_id"] for item in project_lock.get("resolved_domain_packs", [])}
    if resolved_lock_ids != set(confirmed_package["domain_pack_lock_ids"]):
        raise InputAttestationError("Domain Pack Lock closure mismatch", code="STALE_PACK_LOCK")
    for locked in project_lock["resolved_domain_packs"]:
        pack = registry.resolve(locked["pack_id"], locked["pack_version"])
        if pack.lock.lock_id != locked["pack_lock_id"] or pack.lock.content_digest != locked["pack_content_digest"]:
            raise InputAttestationError("Domain Pack Lock is stale or tampered", code="STALE_PACK_LOCK")
        raw = (pack.root / "pack.lock.json").read_bytes()
        records[pack.lock.lock_id] = ResolvedArtifact(
            artifact_id=pack.lock.lock_id,
            relative_path=f"domain-packs/{pack.manifest.pack_id}/pack.lock.json",
            byte_sha256=hashlib.sha256(raw).hexdigest(),
            content_digest=pack.lock.content_digest,
            document=pack.lock.document,
        )
    _verify_authority_closure(confirmed_package, records)
    store = SourceStore(workspace_root)
    for record in records.values():
        if record.document.get("manifest_kind") == "KG_MNP_SOURCE_ASSET":
            store.verify_source(record.artifact_id)
    review = records[confirmed_package["review_decision_log_id"]].document
    if review.get("semantic_decision_hash") != confirmed_package["review_semantic_hash"]:
        raise InputAttestationError("review semantic hash mismatch")
    proposal = records[confirmed_package["source_proposal_id"]].document
    if proposal.get("content_digest") != confirmed_package["source_proposal_digest"]:
        raise InputAttestationError("source proposal digest mismatch")
    package_bytes = confirmed_bytes
    if package_bytes is None:
        package_record = resolver.index.get(confirmed_package["package_id"])
        if package_record is not None:
            package_bytes = (Path(workspace).resolve() / package_record.relative_path).read_bytes()
    if package_bytes is None:
        from zhigou_toolchain.contracts.document_io import deterministic_json_bytes

        package_bytes = deterministic_json_bytes(confirmed_package)
    rows = [
        {"artifact_id": item.artifact_id, "path": item.relative_path, "byte_sha256": item.byte_sha256, "content_digest": item.content_digest}
        for item in sorted(records.values(), key=lambda value: value.artifact_id)
    ]
    counts = {name: len(values) for name, values in partitions.items()}
    core = {
        "manifest_kind": "KG_MNP_COMPILER_INPUT_ATTESTATION",
        "schema_version": "1.0.0",
        "confirmed_package_id": confirmed_package["package_id"],
        "confirmed_package_sha256": hashlib.sha256(package_bytes).hexdigest(),
        "confirmed_package_semantic_digest": confirmed_package["content_digest"],
        "project_lock_id": confirmed_package["project_lock_id"],
        "contract_catalog_digest": catalog.digest,
        "domain_pack_lock_ids": confirmed_package["domain_pack_lock_ids"],
        "scope_id": confirmed_package["scope_id"],
        "scope_approval_id": confirmed_package["scope_approval_id"],
        "competency_question_set_id": confirmed_package["competency_question_set_id"],
        "coverage_report_id": confirmed_package["competency_question_coverage_report_id"],
        "kg_ir_dataset_ids": confirmed_package["kg_ir_dataset_ids"],
        "baseline_snapshot_id": confirmed_package["baseline_snapshot_id"],
        "term_inventory_id": confirmed_package["terminology_catalog_id"],
        "term_alignment_set_id": confirmed_package["term_alignment_set_id"],
        "field_mapping_candidate_set_id": confirmed_package["field_mapping_candidate_set_id"],
        "proposal_id": confirmed_package["source_proposal_id"],
        "prevalidation_report_id": confirmed_package["formal_prevalidation_report_id"],
        "review_policy_id": confirmed_package["review_policy_id"],
        "review_decision_log_id": confirmed_package["review_decision_log_id"],
        "review_semantic_hash": confirmed_package["review_semantic_hash"],
        "resolved_artifacts": rows,
        "partition_counts": counts,
        "closure_results": {
            "evidence_basis_points": confirmed_package["evidence_closure"]["coverage_basis_points"],
            "dependency_basis_points": confirmed_package["dependency_closure"]["coverage_basis_points"],
        },
        "status": "VALID",
        "issues": [],
    }
    return finalize_artifact(core, id_field="attestation_id", urn_kind="compiler-input-attestation", contract="compiler-input-attestation")
