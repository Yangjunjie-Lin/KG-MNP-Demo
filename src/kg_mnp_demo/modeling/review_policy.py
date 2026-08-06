"""Load and validate the frozen Stage 05 review policy."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from .canonical_json import semantic_hash
from .dependencies import REVIEW_POLICY_PATH, ROOT, load_review_policy_document
from .registry import validate_contract
from .semantic_validation import SemanticValidationError

CANDIDATE_DECISIONS = ("CONFIRM", "MODIFY_AND_CONFIRM", "REJECT", "DEFER")
ISSUE_DECISIONS = ("REJECT", "DEFER")
FORBIDDEN_DECISIONS = ("DEPRECATE",)


class ReviewPolicyError(ValueError):
    """The frozen review policy is missing, malformed, or incompatible."""


def validate_review_policy_semantics(policy: Mapping[str, Any]) -> None:
    validate_contract("review-policy", policy)
    errors: list[str] = []
    if policy.get("automatic_decisions") != "FORBIDDEN":
        errors.append("automatic_decisions must be FORBIDDEN")
    if policy.get("default_decision") is not None:
        errors.append("default_decision must be null")
    if policy.get("bulk_confirmation") != "FORBIDDEN":
        errors.append("bulk_confirmation must be FORBIDDEN")
    if sorted(policy.get("candidate_decisions", [])) != sorted(CANDIDATE_DECISIONS):
        errors.append("candidate_decisions must equal the Stage 05 closed set")
    if sorted(policy.get("issue_decisions", [])) != sorted(ISSUE_DECISIONS):
        errors.append("issue_decisions must equal the Stage 05 closed set")
    if policy.get("deprecated_decision_policy") != "FORBIDDEN_IN_DATASET_MODELING":
        errors.append("DEPRECATE must remain forbidden in dataset modeling")
    if policy.get("coverage_policy") != "EVERY_PROPOSAL_ITEM_EXACTLY_ONCE":
        errors.append("coverage_policy must require exact once coverage")
    if policy.get("schema_delta_policy") != "FORBIDDEN":
        errors.append("schema_delta_policy must be FORBIDDEN")
    if policy.get("package_builder_mode") != "DETERMINISTIC":
        errors.append("package_builder_mode must be DETERMINISTIC")
    if errors:
        raise SemanticValidationError(errors)


def load_review_policy(path: Path | None = None) -> dict[str, Any]:
    policy_path = path or REVIEW_POLICY_PATH
    try:
        policy = load_review_policy_document(policy_path)
    except Exception as exc:
        raise ReviewPolicyError(f"cannot load review policy {policy_path}: {exc}") from exc
    try:
        validate_review_policy_semantics(policy)
    except SemanticValidationError as exc:
        raise ReviewPolicyError(str(exc)) from exc
    return policy


@lru_cache(maxsize=1)
def load_default_review_policy() -> dict[str, Any]:
    return load_review_policy()


def review_policy_hash(policy: Mapping[str, Any] | None = None) -> str:
    return semantic_hash(policy if policy is not None else load_default_review_policy())


def decision_allowed_for_target(
    *,
    target_kind: str,
    decision: str,
    policy: Mapping[str, Any] | None = None,
) -> bool:
    active = policy if policy is not None else load_default_review_policy()
    if decision in FORBIDDEN_DECISIONS:
        return False
    if target_kind == "candidate":
        return decision in set(active.get("candidate_decisions", []))
    if target_kind == "issue":
        return decision in set(active.get("issue_decisions", []))
    return False


def project_root() -> Path:
    return ROOT
