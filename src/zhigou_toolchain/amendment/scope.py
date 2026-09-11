"""Input-diff and amendment-scope checks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .diff import compute_cleaned_input_diff, pointer_is_within
from .errors import AmendmentError, AmendmentErrorCode

DATA_LEVEL_TYPES = frozenset(
    {
        "PROPOSE_VALUE_CANDIDATE",
        "PROPOSE_EVIDENCE_ATTACHMENT",
        "PROPOSE_SOURCE_ATTACHMENT",
        "REQUEST_REVIEW_REOPEN",
        "NO_CHANGE_RECOMMENDED",
    }
)


def normalize_pointers(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or (value and not value.startswith("/")):
            raise AmendmentError(
                AmendmentErrorCode.INVALID_REQUEST,
                "JSON pointers must be RFC-6901 strings beginning with '/'",
            )
        if value not in result:
            result.append(value)
    return sorted(result)


def validate_declared_diff(
    base: Mapping[str, Any],
    revised: Mapping[str, Any],
    declared_changed_json_pointers: Iterable[str],
) -> list[str]:
    declared = normalize_pointers(declared_changed_json_pointers)
    actual = compute_cleaned_input_diff(base, revised)
    if actual != declared:
        raise AmendmentError(
            AmendmentErrorCode.UNDECLARED_INPUT_CHANGE,
            f"declared JSON diff {declared!r} does not equal actual diff {actual!r}",
        )
    return actual


def validate_amendment_scope(
    *,
    amendment_type: str,
    actual_changed_json_pointers: Iterable[str],
    declared_changed_json_pointers: Iterable[str],
    target_json_pointers: Iterable[str] = (),
) -> list[str]:
    """Ensure only explicitly approved source pointers changed.

    A target pointer is supplied by a human intake manifest. Phase 05 never
    derives it from an RDF diagnostic path.
    """

    if amendment_type == "PROPOSE_CONSTRAINT_REVIEW":
        raise AmendmentError(
            AmendmentErrorCode.TBOX_AMENDMENT_NOT_EXECUTABLE_IN_PHASE05,
            "constraint/TBox amendments require manual ontology modeling",
        )
    if amendment_type not in DATA_LEVEL_TYPES:
        raise AmendmentError(
            AmendmentErrorCode.INVALID_REQUEST, "unsupported amendment type"
        )
    actual = normalize_pointers(actual_changed_json_pointers)
    declared = normalize_pointers(declared_changed_json_pointers)
    targets = normalize_pointers(target_json_pointers)
    if actual != declared:
        raise AmendmentError(
            AmendmentErrorCode.AMENDMENT_SCOPE_VIOLATION,
            "actual input changes are not the declared amendment scope",
        )
    if amendment_type == "NO_CHANGE_RECOMMENDED" and actual:
        raise AmendmentError(
            AmendmentErrorCode.AMENDMENT_SCOPE_VIOLATION,
            "NO_CHANGE_RECOMMENDED cannot carry changed input",
        )
    if amendment_type == "REQUEST_REVIEW_REOPEN" and actual:
        raise AmendmentError(
            AmendmentErrorCode.AMENDMENT_SCOPE_VIOLATION,
            "REQUEST_REVIEW_REOPEN requires zero input diff",
        )
    if (
        amendment_type
        in {
            "PROPOSE_VALUE_CANDIDATE",
            "PROPOSE_EVIDENCE_ATTACHMENT",
            "PROPOSE_SOURCE_ATTACHMENT",
        }
        and not actual
    ):
        raise AmendmentError(
            AmendmentErrorCode.REENTRY_TARGET_UNRESOLVED,
            "data amendment requires human-supplied changed JSON pointers",
        )
    if targets and any(
        not any(pointer_is_within(pointer, target) for target in targets)
        for pointer in actual
    ):
        raise AmendmentError(
            AmendmentErrorCode.AMENDMENT_SCOPE_VIOLATION,
            "changed pointer falls outside the approved target scope",
        )
    return actual
