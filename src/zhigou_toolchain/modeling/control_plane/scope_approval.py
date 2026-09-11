"""Semantic scope decisions separated from operational review metadata."""

from __future__ import annotations

from typing import Any

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn
from zhigou_toolchain.contracts.registry import validate_contract

from .errors import ScopeInvalidError, ScopeNotApprovedError
from .scope import verify_scope


def approve_scope(
    scope: dict[str, Any],
    *,
    reviewer_id: str,
    reviewer_role: str,
    rationale: str,
    decision: str = "APPROVE",
    decided_at: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    verify_scope(scope)
    if decision not in {"APPROVE", "REJECT", "REQUEST_CHANGES"}:
        raise ScopeInvalidError("invalid scope approval decision")
    if reviewer_role.casefold() in {"provider", "modeling-provider", "llm", "agent"}:
        raise ScopeInvalidError("a provider cannot approve ontology scope")
    semantic = {
        "scope_id": scope["scope_id"], "scope_semantic_hash": scope["content_digest"],
        "reviewer_id": reviewer_id, "reviewer_role": reviewer_role,
        "decision": decision, "rationale": rationale,
    }
    decision_hash = semantic_hash(semantic)
    approval = {
        "manifest_kind": "KG_MNP_ONTOLOGY_SCOPE_APPROVAL", "schema_version": "1.0.0",
        "approval_id": stable_urn("ontology-scope-approval", {"decision_semantic_hash": decision_hash}),
        **semantic,
        "operational_metadata": {"decided_at": decided_at, "display_name": display_name},
        "decision_semantic_hash": decision_hash,
    }
    validate_contract("ontology-scope-approval", approval)
    return approval


def verify_scope_approval(scope: dict[str, Any], approval: dict[str, Any], *, require_approved: bool = True) -> None:
    verify_scope(scope)
    validate_contract("ontology-scope-approval", approval)
    semantic = {
        "scope_id": approval["scope_id"], "scope_semantic_hash": approval["scope_semantic_hash"],
        "reviewer_id": approval["reviewer_id"], "reviewer_role": approval["reviewer_role"],
        "decision": approval["decision"], "rationale": approval["rationale"],
    }
    digest_value = semantic_hash(semantic)
    expected_id = stable_urn("ontology-scope-approval", {"decision_semantic_hash": digest_value})
    if digest_value != approval["decision_semantic_hash"] or expected_id != approval["approval_id"]:
        raise ScopeInvalidError("scope approval semantic record is tampered")
    if approval["scope_id"] != scope["scope_id"] or approval["scope_semantic_hash"] != scope["content_digest"]:
        raise ScopeNotApprovedError("scope approval is STALE")
    if require_approved and approval["decision"] != "APPROVE":
        raise ScopeNotApprovedError("scope is not approved")
