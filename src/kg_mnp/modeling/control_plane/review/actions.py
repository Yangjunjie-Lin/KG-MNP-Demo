"""Core-owned candidate revisions and append-only human review actions."""

from __future__ import annotations

import copy
from typing import Any

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.registry import validate_contract

from ..candidates import recalculate_candidate_identity
from ..errors import ReviewIncompleteError, ReviewPolicyError
from ..limits import ModelingLimits
from ..proposal import verify_proposal
from ..security import assert_safe_json, validate_iri
from .policy import verify_review_policy
from .queue import verify_review_queue

_TERMINAL_CANDIDATE_DECISIONS = {
    "ACCEPT",
    "MODIFY_AND_ACCEPT",
    "REJECT",
    "DEFER",
    "REUSE_EXISTING",
    "MARK_DUPLICATE",
}
_PROVIDER_ROLES = {"provider", "modeling-provider", "llm", "agent"}


def _candidate_index(proposal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = [
        *proposal["tbox_candidates"],
        *proposal["mapping_candidates"],
        *proposal["abox_candidates"],
        *proposal["shacl_candidates"],
    ]
    return {item["candidate_id"]: item for item in candidates}


def rebuild_candidate_revision(
    original: dict[str, Any],
    replacement: dict[str, Any],
    *,
    scope: dict[str, Any] | None = None,
    evidence_ids: set[str] | None = None,
    baseline_element_ids: set[str] | None = None,
    candidate_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Create a new immutable candidate revision and structurally revalidate it."""

    allowed_changes = {
        "candidate_action",
        "body",
        "kg_ir_item_refs",
        "evidence_refs",
        "domain_asset_refs",
        "competency_question_refs",
        "baseline_element_refs",
        "dependency_candidate_refs",
        "rationale",
        "support_status",
        "score_basis",
        "score_basis_points",
    }
    unknown = set(replacement) - allowed_changes - set(original)
    if unknown:
        raise ReviewPolicyError(f"modified candidate has unknown fields: {sorted(unknown)}")
    revision = copy.deepcopy(original)
    for field in allowed_changes:
        if field in replacement:
            revision[field] = copy.deepcopy(replacement[field])
    revision["candidate_kind"] = original["candidate_kind"]
    revision["publication_scope"] = original["publication_scope"]
    revision["review_required"] = True
    for field in (
        "kg_ir_item_refs",
        "evidence_refs",
        "domain_asset_refs",
        "competency_question_refs",
        "baseline_element_refs",
        "provider_snapshot_refs",
        "model_invocation_refs",
        "dependency_candidate_refs",
    ):
        revision[field] = sorted(set(revision[field]))
    assert_safe_json(revision)
    allowed_new = tuple(scope["namespace_policy"]["allowed_new_namespaces"]) if scope else ()
    reusable = tuple(scope["namespace_policy"]["reusable_namespaces"]) if scope else ()
    for field in ("subject_iri", "predicate_iri", "object_iri", "target_iri"):
        value = revision["body"].get(field)
        if value:
            validate_iri(
                value,
                allowed_namespaces=allowed_new,
                reusable_namespaces=reusable,
                creating=(
                    revision["candidate_action"] == "CREATE_NEW"
                    and field in {"subject_iri", "target_iri"}
                ),
            )
    if evidence_ids is not None and not set(revision["evidence_refs"]) <= evidence_ids:
        raise ReviewPolicyError("modified candidate EvidenceRecord closure failed")
    if baseline_element_ids is not None and not set(revision["baseline_element_refs"]) <= baseline_element_ids:
        raise ReviewPolicyError("modified candidate baseline closure failed")
    if candidate_ids is not None and not set(revision["dependency_candidate_refs"]) <= candidate_ids:
        raise ReviewPolicyError("modified candidate dependency closure failed")
    if not revision["evidence_refs"] and not revision["domain_asset_refs"]:
        raise ReviewPolicyError("modified candidate lacks evidence")
    if revision["support_status"] == "UNSUPPORTED":
        raise ReviewPolicyError("modified candidate remains unsupported")
    revision["issues"] = [
        item for item in revision["issues"] if item["severity"] != "BLOCKING"
    ]
    signature, candidate_id = recalculate_candidate_identity(revision)
    if candidate_id == original["candidate_id"]:
        raise ReviewPolicyError("MODIFY_AND_ACCEPT must produce a new Candidate ID")
    revision["semantic_signature"] = signature
    revision["candidate_id"] = candidate_id
    return revision


def _semantic_action_core(action: dict[str, Any]) -> dict[str, Any]:
    modified = action["modified_candidate"]
    return {
        "review_queue_id": action["review_queue_id"],
        "project_lock_id": action["project_lock_id"],
        "sequence": action["sequence"],
        "candidate_id": action["candidate_id"],
        "issue_id": action["issue_id"],
        "decision": action["decision"],
        "reviewer_id": action["reviewer_id"],
        "reviewer_role": action["reviewer_role"],
        "rationale": action["rationale"],
        "modified_candidate_semantic_signature": (
            modified["semantic_signature"] if modified is not None else None
        ),
        "baseline_element_ref": action["baseline_element_ref"],
        "evidence_refs": action["evidence_refs"],
    }


def build_review_action(
    *,
    queue: dict[str, Any],
    proposal: dict[str, Any],
    policy: dict[str, Any],
    existing_actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    decision: str,
    reviewer_id: str,
    reviewer_role: str,
    rationale: str,
    candidate_id: str | None = None,
    issue_id: str | None = None,
    modified_candidate: dict[str, Any] | None = None,
    baseline_element_ref: str | None = None,
    evidence_refs: list[str] | tuple[str, ...] = (),
    decided_at: str | None = None,
    session_id: str | None = None,
    display_name: str | None = None,
    limits: ModelingLimits | None = None,
) -> dict[str, Any]:
    verify_review_queue(queue, proposal=proposal, policy=policy)
    verify_proposal(proposal)
    verify_review_policy(policy, project_lock_id=proposal["project_lock_id"])
    verify_action_chain(existing_actions, queue=queue)
    effective_limits = limits or ModelingLimits()
    if len(existing_actions) >= effective_limits.max_review_actions:
        raise ReviewIncompleteError("review action limit exceeded")
    if reviewer_role.casefold() in _PROVIDER_ROLES:
        raise ReviewPolicyError("a provider cannot perform human review")
    matches = [
        item
        for item in queue["items"]
        if item["candidate_id"] == candidate_id and item["issue_id"] == issue_id
    ]
    if len(matches) != 1:
        raise ReviewPolicyError("review action target is absent or ambiguous")
    item = matches[0]
    candidates = _candidate_index(proposal)
    if candidate_id is not None:
        if decision not in _TERMINAL_CANDIDATE_DECISIONS | {"REQUEST_EVIDENCE", "COMMENT"}:
            raise ReviewPolicyError("decision is not valid for a candidate")
        if reviewer_role not in item["required_roles"]:
            raise ReviewPolicyError("reviewer role is not authorized for this candidate scope")
        if item["blocking_reasons"] and decision in {
            "ACCEPT",
            "MODIFY_AND_ACCEPT",
            "REUSE_EXISTING",
        }:
            raise ReviewPolicyError("a blocking candidate cannot be accepted")
    elif decision not in {"RESOLVE_CONFLICT", "COMMENT"}:
        raise ReviewPolicyError("issue actions only support RESOLVE_CONFLICT or COMMENT")
    if decision == "MODIFY_AND_ACCEPT":
        if modified_candidate is None or candidate_id is None:
            raise ReviewPolicyError("MODIFY_AND_ACCEPT requires a modified candidate")
        original = candidates[candidate_id]
        signature, recalculated_id = recalculate_candidate_identity(modified_candidate)
        if (
            signature != modified_candidate.get("semantic_signature")
            or recalculated_id != modified_candidate.get("candidate_id")
            or recalculated_id == original["candidate_id"]
        ):
            raise ReviewPolicyError("modified candidate was not Core-revised and revalidated")
        if modified_candidate["issues"] or modified_candidate["support_status"] == "UNSUPPORTED":
            raise ReviewPolicyError("modified candidate does not pass revision prevalidation")
    elif modified_candidate is not None:
        raise ReviewPolicyError("modified_candidate is only valid for MODIFY_AND_ACCEPT")
    if decision == "REUSE_EXISTING" and not baseline_element_ref:
        raise ReviewPolicyError("REUSE_EXISTING requires a baseline element reference")
    sequence = len(existing_actions) + 1
    previous_hash = existing_actions[-1]["action_hash"] if existing_actions else None
    action: dict[str, Any] = {
        "manifest_kind": "KG_MNP_ONTOLOGY_REVIEW_ACTION",
        "schema_version": "1.0.0",
        "review_queue_id": queue["review_queue_id"],
        "project_lock_id": queue["project_lock_id"],
        "sequence": sequence,
        "previous_action_hash": previous_hash,
        "candidate_id": candidate_id,
        "issue_id": issue_id,
        "decision": decision,
        "reviewer_id": reviewer_id,
        "reviewer_role": reviewer_role,
        "rationale": rationale,
        "modified_candidate": copy.deepcopy(modified_candidate),
        "baseline_element_ref": baseline_element_ref,
        "evidence_refs": sorted(set(evidence_refs)),
        "operational_metadata": {
            "decided_at": decided_at,
            "session_id": session_id,
            "display_name": display_name,
        },
    }
    assert_safe_json(action)
    action["semantic_action_hash"] = semantic_hash(_semantic_action_core(action))
    action["action_hash"] = semantic_hash(
        {
            "semantic_action_hash": action["semantic_action_hash"],
            "previous_action_hash": previous_hash,
            "operational_metadata": action["operational_metadata"],
        }
    )
    action["action_id"] = stable_urn("ontology-review-action", {"action_hash": action["action_hash"]})
    validate_contract("ontology-review-action", action)
    return action


def verify_review_action(action: dict[str, Any]) -> None:
    validate_contract("ontology-review-action", action)
    if semantic_hash(_semantic_action_core(action)) != action["semantic_action_hash"]:
        raise ReviewIncompleteError("review action semantic hash mismatch")
    expected_hash = semantic_hash(
        {
            "semantic_action_hash": action["semantic_action_hash"],
            "previous_action_hash": action["previous_action_hash"],
            "operational_metadata": action["operational_metadata"],
        }
    )
    expected_id = stable_urn("ontology-review-action", {"action_hash": expected_hash})
    if expected_hash != action["action_hash"] or expected_id != action["action_id"]:
        raise ReviewIncompleteError("review action operational hash mismatch")


def verify_action_chain(
    actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    queue: dict[str, Any] | None = None,
) -> None:
    previous: str | None = None
    seen: set[str] = set()
    for sequence, action in enumerate(actions, start=1):
        verify_review_action(action)
        if action["sequence"] != sequence or action["previous_action_hash"] != previous:
            raise ReviewIncompleteError("review action chain was deleted, reordered, or replayed")
        if action["action_id"] in seen:
            raise ReviewIncompleteError("review action replay detected")
        if queue is not None and (
            action["review_queue_id"] != queue["review_queue_id"]
            or action["project_lock_id"] != queue["project_lock_id"]
        ):
            raise ReviewIncompleteError("cross-project or stale review action")
        seen.add(action["action_id"])
        previous = action["action_hash"]
