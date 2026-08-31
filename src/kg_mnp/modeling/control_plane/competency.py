"""Competency question sets and structural-only coverage reports."""

from __future__ import annotations

from typing import Any

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.contracts.registry import validate_contract

from .artifacts import finalize_document, verify_document
from .errors import ModelingControlError


def build_question_set(*, project_lock_id: str, scope_id: str, questions: list[dict[str, Any]]) -> dict[str, Any]:
    if not questions:
        raise ModelingControlError("competency question set cannot be empty")
    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    for source in questions:
        if not source.get("question_text") or not source.get("purpose"):
            raise ModelingControlError("each competency question needs text and purpose")
        semantic = {
            "question_text": source["question_text"], "purpose": source["purpose"],
            "priority": source.get("priority", "MEDIUM"),
            "expected_answer_shape": source.get("expected_answer_shape", "ENTITY_LIST"),
            "required_concepts": sorted(set(source.get("required_concepts", []))),
            "required_relations": sorted(set(source.get("required_relations", []))),
            "required_constraints": sorted(set(source.get("required_constraints", []))),
            "evidence_refs": sorted(set(source.get("evidence_refs", []))),
            "source_domain_asset_refs": sorted(set(source.get("source_domain_asset_refs", []))),
            "validation_intent": source.get("validation_intent", "RETRIEVAL"),
            "status": source.get("status", "APPROVED"),
        }
        question_id = source.get("question_id") or stable_urn("competency-question", semantic)
        if question_id in ids:
            raise ModelingControlError("duplicate competency question ID")
        ids.add(question_id)
        normalized.append({"question_id": question_id, **semantic})
    core = {
        "manifest_kind": "KG_MNP_COMPETENCY_QUESTION_SET", "schema_version": "1.0.0",
        "project_lock_id": project_lock_id, "scope_id": scope_id,
        "questions": sorted(normalized, key=lambda item: item["question_id"]),
    }
    result = finalize_document(core, id_field="question_set_id", urn_kind="competency-question-set")
    validate_contract("competency-question-set", result)
    return result


def verify_question_set(value: dict[str, Any]) -> None:
    validate_contract("competency-question-set", value)
    verify_document(value, id_field="question_set_id", urn_kind="competency-question-set")
    ids = [item["question_id"] for item in value["questions"]]
    if len(ids) != len(set(ids)):
        raise ModelingControlError("duplicate competency question ID")


def structural_coverage(question_set: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    verify_question_set(question_set)
    candidates = [
        *proposal.get("tbox_candidates", []), *proposal.get("mapping_candidates", []),
        *proposal.get("abox_candidates", []), *proposal.get("shacl_candidates", []),
    ]
    coverage = []
    for question in question_set["questions"]:
        related = sorted(item["candidate_id"] for item in candidates if question["question_id"] in item.get("competency_question_refs", []))
        required = bool(question["required_concepts"] or question["required_relations"] or question["required_constraints"])
        status = "COVERED" if related else ("GAP" if required else "PARTIAL")
        coverage.append({"question_id": question["question_id"], "status": status, "candidate_refs": related, "issue_refs": [], "structural_only": True})
    core = {
        "manifest_kind": "KG_MNP_COMPETENCY_QUESTION_COVERAGE_REPORT", "schema_version": "1.0.0",
        "question_set_id": question_set["question_set_id"], "proposal_id": proposal["proposal_id"],
        "coverage": coverage, "execution_claimed": False,
    }
    result = finalize_document(core, id_field="coverage_report_id", urn_kind="competency-question-coverage-report")
    validate_contract("competency-question-coverage-report", result)
    return result
