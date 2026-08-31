"""Closed review policies with an explicit development-only profile."""

from __future__ import annotations

from typing import Any

from kg_mnp.contracts.registry import validate_contract

from ..artifacts import finalize_document, verify_document
from ..errors import ReviewPolicyError

_PRODUCTION_RULES = {
    "TBOX": (["Domain Expert", "Ontology Engineer"], 2),
    "SHACL": (["Constraint Reviewer", "Ontology Engineer"], 1),
    "MAPPING": (["Data/Knowledge Engineer"], 1),
    "ABOX": (["Data Steward", "Domain Reviewer"], 1),
}


def build_review_policy(
    *,
    project_lock_id: str,
    profile: str = "PRODUCTION_MULTI_ROLE",
) -> dict[str, Any]:
    if profile == "DEVELOPMENT_SINGLE_REVIEWER":
        rules = {scope: (["Development Reviewer"], 1) for scope in _PRODUCTION_RULES}
        development_only = True
        global_minimum = 1
    elif profile == "PRODUCTION_MULTI_ROLE":
        rules = _PRODUCTION_RULES
        development_only = False
        global_minimum = 2
    else:
        raise ReviewPolicyError("unknown ontology review policy profile")
    candidate_scope_rules = [
        {
            "publication_scope": scope,
            "required_roles": sorted(roles),
            "minimum_approvals": minimum,
        }
        for scope, (roles, minimum) in sorted(rules.items())
    ]
    required_roles = sorted({role for roles, _minimum in rules.values() for role in roles})
    core = {
        "manifest_kind": "KG_MNP_ONTOLOGY_REVIEW_POLICY",
        "schema_version": "1.0.0",
        "project_lock_id": project_lock_id,
        "policy_profile": profile,
        "candidate_scope_rules": candidate_scope_rules,
        "required_roles": required_roles,
        "minimum_approvals": global_minimum,
        "evidence_requirements": "DOMAIN_EVIDENCE_ALLOWED",
        "modification_policy": "NEW_REVISION_AND_REVALIDATE",
        "blocking_issue_policy": "MUST_RESOLVE",
        "quorum_policy": "PER_SCOPE",
        "self_approval_policy": "PROVIDER_PROHIBITED",
        "development_only": development_only,
    }
    policy = finalize_document(core, id_field="policy_id", urn_kind="ontology-review-policy")
    validate_contract("ontology-review-policy", policy)
    return policy


def verify_review_policy(
    policy: dict[str, Any],
    *,
    project_lock_id: str | None = None,
) -> None:
    validate_contract("ontology-review-policy", policy)
    verify_document(policy, id_field="policy_id", urn_kind="ontology-review-policy")
    if project_lock_id is not None and policy["project_lock_id"] != project_lock_id:
        raise ReviewPolicyError("review policy is bound to another or stale Project Lock")
    if policy["policy_profile"] == "DEVELOPMENT_SINGLE_REVIEWER" and not policy["development_only"]:
        raise ReviewPolicyError("single-reviewer policy must be marked development-only")
    if policy["policy_profile"] == "PRODUCTION_MULTI_ROLE" and policy["development_only"]:
        raise ReviewPolicyError("production policy cannot be marked development-only")


def rule_for_scope(policy: dict[str, Any], publication_scope: str) -> dict[str, Any]:
    verify_review_policy(policy)
    for rule in policy["candidate_scope_rules"]:
        if rule["publication_scope"] == publication_scope:
            return rule
    raise ReviewPolicyError(f"review policy has no rule for {publication_scope}")
