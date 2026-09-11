"""Closed deployment-governance state machine for Phase 06."""

from __future__ import annotations

from .errors import ActivationError, ActivationErrorCode

TERMINAL_STATES = frozenset({"APPROVED_FOR_ACTIVATION", "REJECTED", "DEFERRED"})
TRANSITIONS = {
    "DRAFT": frozenset({"SUBMITTED"}),
    "SUBMITTED": TERMINAL_STATES,
    "APPROVED_FOR_ACTIVATION": frozenset(),
    "REJECTED": frozenset(),
    "DEFERRED": frozenset(),
}


def require_transition(current: str, target: str) -> None:
    """Require one of the only legal proposal transitions."""

    if target not in TRANSITIONS.get(current, frozenset()):
        raise ActivationError(
            ActivationErrorCode.INVALID_ACTIVATION_REQUEST,
            f"illegal activation proposal transition: {current} -> {target}",
        )
