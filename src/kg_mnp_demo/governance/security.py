"""Loopback HTTP write-boundary policy."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from typing import Any

from .errors import GovernanceError, GovernanceErrorCode

MAX_BODY_BYTES = 64 * 1024
WRITE_ROUTES = (
    "POST /governance/api/proposals",
    "POST /governance/api/proposals/{id}/submit",
    "POST /governance/api/proposals/{id}/review",
)


def csrf_token() -> str:
    """Return ephemeral anti-CSRF entropy; this is not an identity credential."""

    return secrets.token_urlsafe(32)


def exact_fields(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST,
            f"{label} field set mismatch",
        )
    return dict(value)


def proposal_identifier(digest: str) -> str:
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST, "invalid proposal identifier"
        )
    return f"urn:kg-mnp:resolution-proposal:{digest}"
