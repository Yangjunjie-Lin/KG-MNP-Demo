"""Closed ontology modeling proposal assembly."""

from __future__ import annotations

from typing import Any

from kg_mnp.contracts.registry import validate_contract

from .artifacts import finalize_document, verify_document
from .candidates import verify_candidate_set


def build_proposal(
    *,
    project_lock_id: str,
    input_bundle: dict[str, Any],
    scope: dict[str, Any],
    question_set: dict[str, Any],
    baseline: dict[str, Any],
    terminology: dict[str, Any],
    alignments: dict[str, Any],
    field_mappings: dict[str, Any],
    candidate_set: dict[str, Any],
    provider_snapshot_ids: list[str] | tuple[str, ...],
    model_invocation_ids: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    verify_candidate_set(candidate_set)
    partitions = {kind: [] for kind in ("TBOX", "MAPPING", "ABOX", "SHACL")}
    for item in candidate_set["candidates"]:
        partitions[item["candidate_kind"]].append(item)
    candidate_count = len(candidate_set["candidates"])
    with_evidence = sum(bool(item["evidence_refs"] or item["domain_asset_refs"]) for item in candidate_set["candidates"])
    questions = {item["question_id"] for item in question_set["questions"]}
    covered = {ref for item in candidate_set["candidates"] for ref in item["competency_question_refs"]} & questions
    core = {
        "manifest_kind": "KG_MNP_ONTOLOGY_MODELING_PROPOSAL", "schema_version": "1.0.0",
        "project_lock_id": project_lock_id, "modeling_input_bundle_id": input_bundle["modeling_input_bundle_id"],
        "scope_id": scope["scope_id"], "competency_question_set_id": question_set["question_set_id"],
        "baseline_snapshot_id": baseline["baseline_snapshot_id"], "terminology_catalog_id": terminology["terminology_catalog_id"],
        "term_alignment_set_id": alignments["term_alignment_set_id"],
        "field_mapping_candidate_set_id": field_mappings["field_mapping_candidate_set_id"],
        "provider_snapshots": sorted(set(provider_snapshot_ids)), "model_invocation_records": sorted(set(model_invocation_ids)),
        "tbox_candidates": partitions["TBOX"], "mapping_candidates": partitions["MAPPING"],
        "abox_candidates": partitions["ABOX"], "shacl_candidates": partitions["SHACL"],
        "conflicts": candidate_set["conflicts"],
        "issues": sorted([problem for item in candidate_set["candidates"] for problem in item["issues"]], key=lambda item: item["issue_id"]),
        "coverage_summary": {"covered": len(covered), "partial": 0, "gaps": len(questions - covered), "execution_claimed": False},
        "evidence_summary": {"candidate_count": candidate_count, "with_evidence": with_evidence, "coverage_basis_points": 10000 if candidate_count == 0 else with_evidence * 10000 // candidate_count},
        "authority_level": "PROPOSAL_ONLY",
    }
    proposal = finalize_document(core, id_field="proposal_id", urn_kind="ontology-modeling-proposal")
    validate_contract("ontology-modeling-proposal", proposal)
    return proposal


def verify_proposal(value: dict[str, Any]) -> None:
    validate_contract("ontology-modeling-proposal", value)
    verify_document(value, id_field="proposal_id", urn_kind="ontology-modeling-proposal")
    if value["authority_level"] != "PROPOSAL_ONLY":
        raise ValueError("proposal authority boundary violated")
