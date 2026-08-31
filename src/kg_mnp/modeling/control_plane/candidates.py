"""Core-owned candidate normalization, identity, merge, and closure."""

from __future__ import annotations

import copy
from typing import Any

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.registry import validate_contract

from .artifacts import finalize_document, verify_document
from .conflicts import detect_conflicts, issue
from .errors import ModelingControlError, ModelingProposalError
from .limits import ModelingLimits
from .scope import verify_scope
from .security import assert_safe_json, has_mixed_script_confusable, validate_iri

IRI_FIELDS = ("subject_iri", "predicate_iri", "object_iri", "target_iri")
TYPES_BY_SCOPE = {
    "TBOX": {
        "CLASS",
        "OBJECT_PROPERTY",
        "DATA_PROPERTY",
        "SUBCLASS_AXIOM",
        "DOMAIN_AXIOM",
        "RANGE_AXIOM",
        "DISJOINT_CLASSES_AXIOM",
    },
    "MAPPING": {
        "RECORD_TO_CLASS",
        "FIELD_TO_DATA_PROPERTY",
        "REFERENCE_TO_OBJECT_PROPERTY",
        "VALUE_MAPPING",
        "IRI_TEMPLATE",
        "NULL_HANDLING_POLICY",
    },
    "ABOX": {
        "INDIVIDUAL",
        "CLASS_ASSERTION",
        "DATA_PROPERTY_ASSERTION",
        "OBJECT_PROPERTY_ASSERTION",
    },
    "SHACL": {
        "NODE_SHAPE",
        "PROPERTY_SHAPE",
        "MIN_COUNT",
        "MAX_COUNT",
        "DATATYPE",
        "CLASS_CONSTRAINT",
        "NODE_KIND",
        "IN_VALUES",
    },
}


def candidate_semantic_core(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the only fields that define a Core-owned candidate identity."""

    return {
        "candidate_kind": candidate["candidate_kind"],
        "publication_scope": candidate["publication_scope"],
        "candidate_action": candidate["candidate_action"],
        "body": candidate["body"],
    }


def recalculate_candidate_identity(candidate: dict[str, Any]) -> tuple[str, str]:
    signature = semantic_hash(candidate_semantic_core(candidate))
    return signature, stable_urn("ontology-candidate", {"semantic_signature": signature})


def _normalize_one(
    draft: dict[str, Any],
    *,
    provider_snapshot_id: str,
    model_invocation_refs: tuple[str, ...],
    scope: dict[str, Any],
    evidence_ids: set[str],
    kg_ir_item_ids: set[str],
    baseline_element_ids: set[str],
    dependency_map: dict[str, str],
) -> dict[str, Any]:
    assert_safe_json(draft, provider_output=True)
    body = copy.deepcopy(draft["body"])
    allowed_namespaces = tuple(scope["namespace_policy"]["allowed_new_namespaces"])
    reusable = tuple(scope["namespace_policy"]["reusable_namespaces"])
    creating = draft["candidate_action"] == "CREATE_NEW"
    problems: list[dict[str, Any]] = []
    namespace_problem = False
    for field in IRI_FIELDS:
        value = body.get(field)
        if value:
            try:
                validate_iri(value, allowed_namespaces=allowed_namespaces, reusable_namespaces=reusable, creating=creating and field in {"subject_iri", "target_iri"})
            except ModelingControlError as exc:
                if "authorized namespaces" not in str(exc) and "read-only" not in str(exc):
                    raise
                namespace_problem = True
    evidence_refs = sorted(set(draft.get("evidence_refs", [])))
    kg_refs = sorted(set(draft.get("kg_ir_item_refs", [])))
    baseline_refs = sorted(set(draft.get("baseline_element_refs", [])))
    if not set(evidence_refs).issubset(evidence_ids):
        raise ModelingProposalError("provider draft has dangling EvidenceRecord reference")
    if not set(kg_refs).issubset(kg_ir_item_ids):
        raise ModelingProposalError("provider draft has dangling KG-IR reference")
    if not set(baseline_refs).issubset(baseline_element_ids):
        raise ModelingProposalError("provider draft has dangling baseline reference")
    semantic_core = {
        "candidate_kind": draft["draft_kind"], "publication_scope": draft["draft_kind"],
        "candidate_action": draft["candidate_action"], "body": body,
    }
    signature = semantic_hash(semantic_core)
    candidate_id = stable_urn("ontology-candidate", {"semantic_signature": signature})
    dependencies = [dependency_map.get(value, value) for value in draft.get("dependency_draft_refs", [])]
    support = draft.get("support_status", "SUPPORTED")
    if draft["draft_kind"] not in scope["target_artifacts"]:
        support = "UNSUPPORTED"
        problems.append(
            issue(
                "OUT_OF_SCOPE_CANDIDATE",
                "candidate publication scope is outside the approved Ontology Scope",
                [candidate_id],
                evidence_refs=evidence_refs,
            )
        )
    if body["candidate_type"] not in TYPES_BY_SCOPE[draft["draft_kind"]]:
        support = "UNSUPPORTED"
        problems.append(
            issue(
                "ELEMENT_TYPE_CONFLICT",
                "candidate type does not belong to its closed publication partition",
                [candidate_id],
                evidence_refs=evidence_refs,
            )
        )
    if namespace_problem:
        support = "UNSUPPORTED"
        problems.append(
            issue(
                "UNAUTHORIZED_NAMESPACE",
                "candidate IRI is outside an authorized namespace or redefines a reserved namespace",
                [candidate_id],
                evidence_refs=evidence_refs,
            )
        )
    text_values = [
        value
        for value in (body.get("label"), draft.get("rationale"))
        if isinstance(value, str)
    ]
    if any(has_mixed_script_confusable(value) for value in text_values):
        problems.append(
            issue(
                "UNICODE_HOMOGLYPH_RISK",
                "mixed Latin/Greek/Cyrillic text requires explicit human inspection",
                [candidate_id],
                severity="WARNING",
                evidence_refs=evidence_refs,
            )
        )
    if not evidence_refs and not draft.get("domain_asset_refs"):
        support = "UNSUPPORTED"
        problems.append(issue("EVIDENCE_MISSING", "candidate has neither EvidenceRecord nor domain modeling evidence", [candidate_id], evidence_refs=evidence_refs))
    if support == "UNSUPPORTED":
        problems.append(issue("UNSUPPORTED_CANDIDATE", "unsupported candidate cannot enter a confirmed package", [candidate_id], evidence_refs=evidence_refs))
    return {
        "candidate_id": candidate_id, "candidate_kind": draft["draft_kind"],
        "publication_scope": draft["draft_kind"], "candidate_action": draft["candidate_action"],
        "semantic_signature": signature, "kg_ir_item_refs": kg_refs, "evidence_refs": evidence_refs,
        "domain_asset_refs": sorted(set(draft.get("domain_asset_refs", []))),
        "competency_question_refs": sorted(set(draft.get("competency_question_refs", []))),
        "baseline_element_refs": baseline_refs, "provider_snapshot_refs": [provider_snapshot_id],
        "model_invocation_refs": sorted(set(model_invocation_refs)),
        "dependency_candidate_refs": sorted(set(dependencies)), "rationale": draft["rationale"],
        "provider_rationales": [{"provider_snapshot_id": provider_snapshot_id, "rationale": draft["rationale"]}],
        "support_status": support,
        "score_basis": draft.get("score_basis", "provider ordering basis; not semantic correctness probability"),
        "score_basis_points": int(draft.get("score_basis_points", 0)), "review_required": True,
        "issues": sorted(problems, key=lambda item: item["issue_id"]), "body": body,
    }


def normalize_candidate_drafts(
    provider_batches: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    scope: dict[str, Any],
    evidence_ids: set[str],
    kg_ir_item_ids: set[str],
    baseline_element_ids: set[str],
    model_invocation_refs_by_response: dict[str, tuple[str, ...]] | None = None,
    limits: ModelingLimits | None = None,
) -> dict[str, Any]:
    verify_scope(scope)
    effective_limits = limits or ModelingLimits()
    total = sum(len(batch["candidate_drafts"]) for batch in provider_batches)
    if total > effective_limits.max_total_candidates:
        raise ModelingProposalError("candidate count limit exceeded")
    normalized: list[dict[str, Any]] = []
    request_ids: list[str] = []
    for batch in provider_batches:
        validate_contract("modeling-provider-response", batch)
        if batch["authority_level"] != "PROPOSAL_ONLY":
            raise ModelingProposalError("provider attempted to exceed proposal authority")
        request_ids.append(batch["request_id"])
        provider_id = batch["provider_snapshot_id"]
        invocation_refs = (model_invocation_refs_by_response or {}).get(
            batch["response_id"], ()
        )
        local_map: dict[str, str] = {}
        for draft in batch["candidate_drafts"]:
            semantic_core = {"candidate_kind": draft["draft_kind"], "publication_scope": draft["draft_kind"], "candidate_action": draft["candidate_action"], "body": draft["body"]}
            local_map[draft["draft_ref"]] = stable_urn("ontology-candidate", {"semantic_signature": semantic_hash(semantic_core)})
        for draft in batch["candidate_drafts"]:
            if len(draft.get("dependency_draft_refs", [])) > effective_limits.max_candidate_dependencies:
                raise ModelingProposalError("candidate dependency limit exceeded")
            normalized.append(_normalize_one(draft, provider_snapshot_id=provider_id, model_invocation_refs=invocation_refs, scope=scope, evidence_ids=evidence_ids, kg_ir_item_ids=kg_ir_item_ids, baseline_element_ids=baseline_element_ids, dependency_map=local_map))
    merged: dict[str, dict[str, Any]] = {}
    for candidate in sorted(normalized, key=lambda item: (item["semantic_signature"], item["candidate_id"])):
        existing = merged.get(candidate["semantic_signature"])
        if existing is None:
            merged[candidate["semantic_signature"]] = candidate
            continue
        for field in ["kg_ir_item_refs", "evidence_refs", "domain_asset_refs", "competency_question_refs", "baseline_element_refs", "provider_snapshot_refs", "model_invocation_refs", "dependency_candidate_refs"]:
            existing[field] = sorted(set(existing[field]) | set(candidate[field]))
        rationales = {
            (item["provider_snapshot_id"], item["rationale"]): item
            for item in [*existing["provider_rationales"], *candidate["provider_rationales"]]
        }
        existing["provider_rationales"] = [
            rationales[key] for key in sorted(rationales)
        ]
        existing["issues"] = sorted({item["issue_id"]: item for item in [*existing["issues"], *candidate["issues"]]}.values(), key=lambda item: item["issue_id"])
        statuses = {existing["support_status"], candidate["support_status"]}
        existing["support_status"] = "UNSUPPORTED" if "UNSUPPORTED" in statuses else ("PARTIALLY_SUPPORTED" if "PARTIALLY_SUPPORTED" in statuses else "SUPPORTED")
    candidates = sorted(merged.values(), key=lambda item: item["candidate_id"])
    candidate_ids = {item["candidate_id"] for item in candidates}
    for candidate in candidates:
        missing = set(candidate["dependency_candidate_refs"]) - candidate_ids
        if missing:
            candidate["issues"].append(issue("CANDIDATE_DEPENDENCY_MISSING", "candidate dependency is absent from normalized set", [candidate["candidate_id"], *sorted(missing)]))
            candidate["support_status"] = "UNSUPPORTED"
    conflicts = detect_conflicts(candidates)
    if len(conflicts) > effective_limits.max_conflicts:
        raise ModelingProposalError("conflict count limit exceeded")
    core = {
        "manifest_kind": "KG_MNP_ONTOLOGY_CANDIDATE_SET", "schema_version": "1.0.0",
        "request_ids": sorted(set(request_ids)), "candidates": candidates, "conflicts": conflicts,
    }
    result = finalize_document(core, id_field="candidate_set_id", urn_kind="ontology-candidate-set")
    validate_contract("ontology-candidate-set", result)
    return result


def verify_candidate_set(value: dict[str, Any]) -> None:
    validate_contract("ontology-candidate-set", value)
    verify_document(value, id_field="candidate_set_id", urn_kind="ontology-candidate-set")
    for candidate in value["candidates"]:
        signature, candidate_id = recalculate_candidate_identity(candidate)
        if signature != candidate["semantic_signature"] or candidate_id != candidate["candidate_id"]:
            raise ModelingProposalError("candidate identity mismatch")
        if not candidate["review_required"]:
            raise ModelingProposalError("candidate bypasses human review")
