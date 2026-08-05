"""Deterministic construction of review-only modeling issues."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .identifiers import issue_id

ISSUE_TYPES = frozenset(
    {
        "MISSING_INFORMATION",
        "CONFLICT",
        "AMBIGUOUS",
        "UNSUPPORTED",
        "INCONSISTENT_SOURCE",
        "LOW_CONFIDENCE",
    }
)
ISSUE_SEVERITIES = frozenset({"INFO", "WARNING", "ERROR", "BLOCKING"})


def make_issue(
    issue_type: str,
    severity: str,
    description: str,
    *,
    source_paths: Iterable[str] = (),
    source_refs: Iterable[str] = (),
    related_candidate_ids: Iterable[str] = (),
    blocking: bool = False,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if issue_type not in ISSUE_TYPES:
        raise ValueError(f"unsupported issue type: {issue_type}")
    if severity not in ISSUE_SEVERITIES:
        raise ValueError(f"unsupported issue severity: {severity}")
    value: dict[str, Any] = {
        "issue_type": issue_type,
        "severity": severity,
        "review_status": "PROPOSED",
        "publication_scope": "REVIEW_ONLY",
        "source_paths": sorted(set(source_paths)),
        "source_refs": sorted(set(source_refs)),
        "related_candidate_ids": sorted(set(related_candidate_ids)),
        "description": description,
        "blocking": bool(blocking),
    }
    if details is not None:
        value["details"] = dict(details)
    value["issue_id"] = issue_id(value)
    return value


def issue_sort_key(issue: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        issue.get("issue_type", ""),
        issue.get("severity", ""),
        tuple(issue.get("source_paths", [])),
        issue.get("issue_id", ""),
    )

