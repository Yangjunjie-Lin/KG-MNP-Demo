"""Validate and normalize explicit human Review Actions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .identifiers import candidate_id
from .registry import validate_contract
from .review_identifiers import review_decision_id
from .review_policy import decision_allowed_for_target, load_default_review_policy
from .semantic_validation import SemanticValidationError


SOURCE_FIELDS = (
    "source_paths",
    "business_fact_evidence_refs",
    "modeling_evidence_refs",
    "mapping_rule_ids",
)

FORBIDDEN_INSTANCE_PREFIXES = (
    "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/",
    "https://yangjunjie-lin.github.io/KG-MNP-Demo/shapes",
    "http://example.org/",
    "https://example.org/",
    "file://",
)


def action_target_id(action: Mapping[str, Any]) -> str:
    target = action.get("target") or {}
    if "candidate_id" in target and "issue_id" in target:
        raise SemanticValidationError(["action target cannot include both candidate_id and issue_id"])
    if "candidate_id" in target:
        return str(target["candidate_id"])
    if "issue_id" in target:
        return str(target["issue_id"])
    raise SemanticValidationError(["action target must include candidate_id or issue_id"])


def action_target_kind(action: Mapping[str, Any]) -> str:
    target = action.get("target") or {}
    if "candidate_id" in target:
        return "candidate"
    if "issue_id" in target:
        return "issue"
    raise SemanticValidationError(["action target must include candidate_id or issue_id"])


def validate_instance_iri(iri: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(iri, str) or not iri:
        return ["proposed_iri must be a non-empty absolute IRI"]
    if "\\" in iri or ":/" in iri and iri[1:3] == ":/":
        errors.append(f"proposed_iri must not contain a local filesystem path: {iri}")
    lowered = iri.lower()
    if "example.org" in lowered:
        errors.append(f"proposed_iri must not use example.org: {iri}")
    if lowered.startswith("file:"):
        errors.append(f"proposed_iri must not use file://: {iri}")
    for forbidden_namespace in FORBIDDEN_INSTANCE_PREFIXES:
        if iri.startswith(forbidden_namespace):
            errors.append(
                f"proposed_iri must not use reserved namespace {forbidden_namespace}: {iri}"
            )
    if not (iri.startswith("http://") or iri.startswith("https://") or iri.startswith("urn:")):
        errors.append(f"proposed_iri must be an absolute http(s) IRI or URN: {iri}")
    return errors


def validate_modified_candidate(
    original: Mapping[str, Any],
    modified: Mapping[str, Any],
    *,
    term_types: Mapping[str, str] | None = None,
) -> None:
    errors: list[str] = []
    if modified.get("review_status") != "PROPOSED":
        errors.append("modified_candidate.review_status must remain PROPOSED")
    if modified.get("publication_scope") != "ABOX":
        errors.append("modified_candidate.publication_scope must remain ABOX")
    original_kind = original.get("candidate_kind", "ENTITY")
    modified_kind = modified.get("candidate_kind", "ENTITY")
    if original_kind != modified_kind:
        errors.append(
            f"modified_candidate.candidate_kind must remain {original_kind!r}, got {modified_kind!r}"
        )
    for field in SOURCE_FIELDS:
        original_values = list(original.get(field, []))
        modified_values = list(modified.get(field, []))
        if not set(original_values).issubset(set(modified_values)):
            errors.append(f"modified_candidate must preserve original {field}")
    expected_id = candidate_id(modified)
    if modified.get("candidate_id") != expected_id:
        errors.append("modified_candidate.candidate_id does not match its semantic content")
    if "proposed_iri" in modified:
        errors.extend(validate_instance_iri(str(modified["proposed_iri"])))
    if term_types is not None:
        errors.extend(validate_candidate_term_types(modified, term_types))
    if errors:
        raise SemanticValidationError(errors)


def validate_candidate_term_types(
    candidate: Mapping[str, Any],
    term_types: Mapping[str, str],
) -> list[str]:
    errors: list[str] = []
    kind = candidate.get("candidate_kind", "ENTITY")
    if kind == "ENTITY" or kind == "CLASS_ASSERTION":
        class_iri = candidate.get("class_iri")
        if not isinstance(class_iri, str):
            errors.append("candidate class_iri is required for type validation")
        elif term_types.get(class_iri) != "Class":
            errors.append(f"class_iri must identify an owl:Class term: {class_iri}")
    elif kind == "OBJECT_PROPERTY_ASSERTION":
        predicate = candidate.get("predicate_iri")
        if term_types.get(predicate) != "ObjectProperty":
            errors.append(
                f"OBJECT_PROPERTY_ASSERTION.predicate_iri must be owl:ObjectProperty: {predicate}"
            )
    elif kind == "DATA_PROPERTY_ASSERTION":
        predicate = candidate.get("predicate_iri")
        if term_types.get(predicate) != "DatatypeProperty":
            errors.append(
                f"DATA_PROPERTY_ASSERTION.predicate_iri must be owl:DatatypeProperty: {predicate}"
            )
    elif kind == "MAPPING_ASSERTION":
        predicate = candidate.get("predicate_iri")
        if term_types.get(predicate) != "ObjectProperty":
            errors.append(
                "MAPPING_ASSERTION.predicate_iri must be owl:ObjectProperty "
                f"under Stage 05 mapping_assertion_term_policy: {predicate}"
            )
    return errors


def validate_review_action(
    action: Mapping[str, Any],
    proposal: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
    term_types: Mapping[str, str] | None = None,
) -> None:
    validate_contract("review-action", action)
    active = policy if policy is not None else load_default_review_policy()
    errors: list[str] = []
    if action.get("proposal_id") != proposal.get("proposal_id"):
        errors.append("review action proposal_id does not match proposal")
    if action.get("proposal_semantic_hash") != proposal.get("proposal_semantic_hash"):
        errors.append("review action proposal_semantic_hash does not match proposal")
    if "decision_id" in action:
        errors.append("review action must not author decision_id")
    if not action.get("rationale"):
        errors.append("review action rationale is required")
    if not action.get("decided_at"):
        errors.append("review action decided_at is required")
    if not action.get("reviewer_id"):
        errors.append("review action reviewer_id is required")
    if action.get("decision") is None:
        errors.append("review action decision is required")

    target_kind = action_target_kind(action)
    target_id = action_target_id(action)
    decision = str(action.get("decision"))
    if not decision_allowed_for_target(
        target_kind=target_kind,
        decision=decision,
        policy=active,
    ):
        errors.append(f"decision {decision!r} is not allowed for {target_kind} targets")

    candidates = {
        item["candidate_id"]: item
        for item in [
            *proposal.get("candidate_entities", []),
            *proposal.get("candidate_assertions", []),
        ]
    }
    issues = {item["issue_id"]: item for item in proposal.get("issues", [])}
    if target_kind == "candidate" and target_id not in candidates:
        errors.append(f"unknown candidate_id: {target_id}")
    if target_kind == "issue" and target_id not in issues:
        errors.append(f"unknown issue_id: {target_id}")

    if decision == "MODIFY_AND_CONFIRM":
        if target_kind != "candidate":
            errors.append("MODIFY_AND_CONFIRM is only allowed for candidate targets")
        modified = action.get("modified_candidate")
        if not isinstance(modified, Mapping):
            errors.append("MODIFY_AND_CONFIRM requires modified_candidate")
        elif target_id in candidates:
            try:
                validate_modified_candidate(
                    candidates[target_id],
                    modified,
                    term_types=term_types,
                )
            except SemanticValidationError as exc:
                errors.extend(exc.errors)
    elif "modified_candidate" in action:
        errors.append("modified_candidate is only allowed for MODIFY_AND_CONFIRM")

    if errors:
        raise SemanticValidationError(errors)


def action_to_decision(
    action: Mapping[str, Any],
    proposal: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
    term_types: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    validate_review_action(
        action,
        proposal,
        policy=policy,
        term_types=term_types,
    )
    target_id = action_target_id(action)
    decision = {
        "decision": action["decision"],
        "rationale": action["rationale"],
        "reviewer_id": action["reviewer_id"],
        "decided_at": action["decided_at"],
        "evidence_refs": sorted(action.get("evidence_refs") or []),
    }
    if "candidate_id" in action["target"]:
        decision["candidate_id"] = action["target"]["candidate_id"]
    else:
        decision["issue_id"] = action["target"]["issue_id"]
    if action["decision"] == "MODIFY_AND_CONFIRM":
        decision["modified_candidate"] = deepcopy(action["modified_candidate"])
    decision["decision_id"] = review_decision_id(
        proposal_id=str(proposal["proposal_id"]),
        target_id=target_id,
        decision=str(action["decision"]),
        rationale=str(action["rationale"]),
        reviewer_id=str(action["reviewer_id"]),
        decided_at=str(action["decided_at"]),
        evidence_refs=list(decision["evidence_refs"]),
        modified_candidate=decision.get("modified_candidate"),
    )
    return decision
