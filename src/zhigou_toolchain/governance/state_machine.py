"""Frozen ResolutionProposal transition policy."""

from __future__ import annotations

from .errors import GovernanceError, GovernanceErrorCode

TERMINAL_STATES = frozenset({"APPROVED_FOR_AMENDMENT", "REJECTED", "DEFERRED"})
TRANSITIONS = {
    ("DRAFT", "SUBMITTED"),
    ("SUBMITTED", "APPROVED_FOR_AMENDMENT"),
    ("SUBMITTED", "REJECTED"),
    ("SUBMITTED", "DEFERRED"),
}


def require_transition(current: str, target: str) -> None:
    if current in TERMINAL_STATES:
        raise GovernanceError(GovernanceErrorCode.TERMINAL_STATE_IMMUTABLE)
    if (current, target) not in TRANSITIONS:
        raise GovernanceError(GovernanceErrorCode.ILLEGAL_STATE_TRANSITION)
