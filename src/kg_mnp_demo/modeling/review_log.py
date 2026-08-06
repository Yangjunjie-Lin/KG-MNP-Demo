"""File-based ReviewDecisionLog workflow without automatic decisions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from .registry import validate_contract
from .review_actions import action_to_decision, action_target_id
from .review_identifiers import (
    decision_log_hash,
    decision_log_id,
    review_decision_id,
    review_session_id,
)
from .review_policy import load_default_review_policy
from .semantic_validation import SemanticValidationError

try:
    from jsonschema import ValidationError as JsonSchemaValidationError
except ImportError:  # pragma: no cover
    JsonSchemaValidationError = Exception  # type: ignore[misc, assignment]


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def proposal_candidate_ids(proposal: Mapping[str, Any]) -> list[str]:
    return [
        item["candidate_id"]
        for item in [
            *proposal.get("candidate_entities", []),
            *proposal.get("candidate_assertions", []),
        ]
    ]


def proposal_issue_ids(proposal: Mapping[str, Any]) -> list[str]:
    return [item["issue_id"] for item in proposal.get("issues", [])]


def decision_target_id(decision: Mapping[str, Any]) -> str:
    if "candidate_id" in decision and "issue_id" in decision:
        raise SemanticValidationError(["decision cannot target both candidate and issue"])
    if "candidate_id" in decision:
        return str(decision["candidate_id"])
    if "issue_id" in decision:
        return str(decision["issue_id"])
    raise SemanticValidationError(["decision must target candidate_id or issue_id"])


def decision_sort_key(decision: Mapping[str, Any]) -> tuple[str, str, str, str]:
    target = decision_target_id(decision)
    target_type = "candidate" if "candidate_id" in decision else "issue"
    return (
        target_type,
        target,
        str(decision.get("decided_at", "")),
        str(decision.get("decision_id", "")),
    )


def sort_decisions(decisions: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [deepcopy(dict(item)) for item in sorted(decisions, key=decision_sort_key)]


def review_coverage(
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_ids = set(proposal_candidate_ids(proposal))
    issue_ids = set(proposal_issue_ids(proposal))
    decided_candidates: list[str] = []
    decided_issues: list[str] = []
    unknown: list[str] = []
    seen: list[str] = []
    duplicates: list[str] = []
    for decision in decision_log.get("decisions", []):
        target = decision.get("candidate_id") or decision.get("issue_id")
        if not isinstance(target, str):
            continue
        if target in seen:
            duplicates.append(target)
        seen.append(target)
        if "candidate_id" in decision:
            if target in candidate_ids:
                decided_candidates.append(target)
            else:
                unknown.append(target)
        elif "issue_id" in decision:
            if target in issue_ids:
                decided_issues.append(target)
            else:
                unknown.append(target)
    undecided_candidates = sorted(candidate_ids - set(decided_candidates))
    undecided_issues = sorted(issue_ids - set(decided_issues))
    coverage_complete = (
        not undecided_candidates
        and not undecided_issues
        and not duplicates
        and not unknown
        and len(decided_candidates) == len(candidate_ids)
        and len(decided_issues) == len(issue_ids)
    )
    return {
        "candidate_count": len(candidate_ids),
        "issue_count": len(issue_ids),
        "decision_count": len(decision_log.get("decisions", [])),
        "decided_candidate_count": len(set(decided_candidates)),
        "decided_issue_count": len(set(decided_issues)),
        "undecided_candidate_ids": undecided_candidates,
        "undecided_issue_ids": undecided_issues,
        "duplicate_target_ids": sorted(set(duplicates)),
        "unknown_target_ids": sorted(set(unknown)),
        "coverage_complete": coverage_complete,
    }


def is_log_completed(decision_log: Mapping[str, Any]) -> bool:
    session = decision_log.get("review_session") or {}
    return isinstance(session.get("completed_at"), str) and bool(session["completed_at"])


def init_review_decision_log(
    proposal: Mapping[str, Any],
    *,
    reviewer_id: str,
    display_name: str,
    role: str,
    started_at: str,
    session_label: str | None = None,
    affiliation: str | None = None,
    review_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    policy = review_policy if review_policy is not None else load_default_review_policy()
    session = review_session_id(
        proposal_id=str(proposal["proposal_id"]),
        proposal_semantic_hash=str(proposal["proposal_semantic_hash"]),
        reviewer_id=reviewer_id,
        started_at=started_at,
        review_policy_id=str(policy["policy_id"]),
        review_policy_version=str(policy["policy_version"]),
        session_label=session_label,
    )
    log_id = decision_log_id(
        proposal_id=str(proposal["proposal_id"]),
        proposal_semantic_hash=str(proposal["proposal_semantic_hash"]),
        reviewer_id=reviewer_id,
        session_id=session,
        review_policy_version=str(policy["policy_version"]),
    )
    reviewer: dict[str, Any] = {
        "reviewer_id": reviewer_id,
        "display_name": display_name,
        "role": role,
    }
    if affiliation:
        reviewer["affiliation"] = affiliation
    draft = {
        "contract_version": "1.0",
        "decision_log_id": log_id,
        "proposal_id": proposal["proposal_id"],
        "proposal_semantic_hash": proposal["proposal_semantic_hash"],
        "reviewer": reviewer,
        "review_session": {
            "session_id": session,
            "started_at": started_at,
        },
        "decisions": [],
    }
    draft["log_hash"] = decision_log_hash(draft)
    validate_contract("review-decision-log", draft)
    return draft


def record_review_action(
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
    action: Mapping[str, Any],
    *,
    review_policy: Mapping[str, Any] | None = None,
    term_types: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if is_log_completed(decision_log):
        raise SemanticValidationError(
            ["completed ReviewDecisionLog cannot accept additional decisions"]
        )
    from .semantic_validation import validate_review_decision_log_semantics

    validate_review_decision_log_semantics(
        decision_log,
        proposal,
        review_policy=review_policy,
        require_final=False,
        verify_draft_integrity=True,
        term_types=term_types,
    )
    if decision_log.get("proposal_id") != proposal.get("proposal_id"):
        raise SemanticValidationError(["decision log proposal_id does not match proposal"])
    if decision_log.get("proposal_semantic_hash") != proposal.get("proposal_semantic_hash"):
        raise SemanticValidationError(
            ["decision log proposal_semantic_hash does not match proposal"]
        )
    reviewer_id = decision_log.get("reviewer", {}).get("reviewer_id")
    if action.get("reviewer_id") != reviewer_id:
        raise SemanticValidationError(
            ["action reviewer_id does not match decision log reviewer"]
        )
    decision = action_to_decision(
        action,
        proposal,
        policy=review_policy,
        term_types=term_types,
    )
    target = action_target_id(action)
    existing = {
        decision_target_id(item)
        for item in decision_log.get("decisions", [])
    }
    if target in existing:
        raise SemanticValidationError([f"duplicate decision target: {target}"])
    next_log = deepcopy(dict(decision_log))
    next_log["decisions"] = sort_decisions([*next_log.get("decisions", []), decision])
    next_log["log_hash"] = decision_log_hash(next_log)
    validate_contract("review-decision-log", next_log)
    return next_log


def review_status(
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
) -> dict[str, Any]:
    coverage = review_coverage(proposal, decision_log)
    issues = {item["issue_id"]: item for item in proposal.get("issues", [])}
    blocking_deferred: list[str] = []
    blocking_undecided: list[str] = []
    for issue_id, issue in issues.items():
        if not issue.get("blocking"):
            continue
        decided = next(
            (
                item
                for item in decision_log.get("decisions", [])
                if item.get("issue_id") == issue_id
            ),
            None,
        )
        if decided is None:
            blocking_undecided.append(issue_id)
        elif decided.get("decision") == "DEFER":
            blocking_deferred.append(issue_id)
    can_finalize = coverage["coverage_complete"] and not is_log_completed(decision_log)
    return {
        **coverage,
        "blocking_undecided_issue_ids": sorted(blocking_undecided),
        "blocking_deferred_issue_ids": sorted(blocking_deferred),
        "log_completed": is_log_completed(decision_log),
        "can_finalize": can_finalize,
    }


def finalize_review_decision_log(
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
    *,
    completed_at: str,
    review_policy: Mapping[str, Any] | None = None,
    term_types: Mapping[str, str] | None = None,
    cleaned_partial_data: Mapping[str, Any] | None = None,
    ontology_baseline: Mapping[str, Any] | None = None,
    mapping_rules: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if is_log_completed(decision_log):
        raise SemanticValidationError(["ReviewDecisionLog is already completed"])
    policy = review_policy if review_policy is not None else load_default_review_policy()
    coverage = review_coverage(proposal, decision_log)
    if not coverage["coverage_complete"]:
        raise SemanticValidationError(
            [
                "cannot finalize incomplete review coverage: "
                f"undecided_candidates={coverage['undecided_candidate_ids']}, "
                f"undecided_issues={coverage['undecided_issue_ids']}, "
                f"duplicates={coverage['duplicate_target_ids']}, "
                f"unknown={coverage['unknown_target_ids']}"
            ]
        )
    started_at = decision_log["review_session"]["started_at"]
    if _parse_datetime(completed_at) < _parse_datetime(started_at):
        raise SemanticValidationError(["completed_at must not be earlier than started_at"])
    for decision in decision_log.get("decisions", []):
        decided_at = decision.get("decided_at")
        if not isinstance(decided_at, str):
            raise SemanticValidationError(["decision decided_at is required"])
        when = _parse_datetime(decided_at)
        if when < _parse_datetime(started_at) or when > _parse_datetime(completed_at):
            raise SemanticValidationError(
                [f"decided_at outside review session range: {decision_target_id(decision)}"]
            )
        expected = review_decision_id(
            proposal_id=str(proposal["proposal_id"]),
            target_id=decision_target_id(decision),
            decision=str(decision["decision"]),
            rationale=str(decision["rationale"]),
            reviewer_id=str(decision["reviewer_id"]),
            decided_at=str(decision["decided_at"]),
            evidence_refs=list(decision.get("evidence_refs") or []),
            modified_candidate=decision.get("modified_candidate"),
        )
        if decision.get("decision_id") != expected:
            raise SemanticValidationError(
                [f"decision_id does not match semantic content: {decision.get('decision_id')}"]
            )

    expected_log_id = decision_log_id(
        proposal_id=str(proposal["proposal_id"]),
        proposal_semantic_hash=str(proposal["proposal_semantic_hash"]),
        reviewer_id=str(decision_log["reviewer"]["reviewer_id"]),
        session_id=str(decision_log["review_session"]["session_id"]),
        review_policy_version=str(policy["policy_version"]),
    )
    if decision_log.get("decision_log_id") != expected_log_id:
        raise SemanticValidationError(["decision_log_id does not match review session binding"])

    final_log = deepcopy(dict(decision_log))
    final_log["decisions"] = sort_decisions(list(final_log.get("decisions", [])))
    final_log["review_session"] = {
        **final_log["review_session"],
        "completed_at": completed_at,
    }
    final_log["log_hash"] = decision_log_hash(final_log)
    try:
        validate_contract("review-decision-log", final_log)
    except JsonSchemaValidationError as exc:
        raise SemanticValidationError(
            [f"final ReviewDecisionLog schema validation failed: {exc.message}"]
        ) from exc

    from .package_validation import load_term_type_index
    from .semantic_validation import validate_review_decision_log_semantics

    types = dict(term_types) if term_types is not None else load_term_type_index()
    validate_review_decision_log_semantics(
        final_log,
        proposal,
        cleaned_partial_data=cleaned_partial_data,
        ontology_baseline=ontology_baseline,
        mapping_rules=mapping_rules,
        review_policy=policy,
        require_final=True,
        term_types=types,
    )
    return final_log
