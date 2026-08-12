"""Fail-closed governance errors with stable HTTP outcomes."""

from __future__ import annotations

from enum import StrEnum


class GovernanceErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_PROPOSAL_TYPE = "INVALID_PROPOSAL_TYPE"
    UNKNOWN_DIAGNOSTIC = "UNKNOWN_DIAGNOSTIC"
    AUTHORITY_MISMATCH = "AUTHORITY_MISMATCH"
    STALE_DIAGNOSTIC_BINDING = "STALE_DIAGNOSTIC_BINDING"
    ILLEGAL_STATE_TRANSITION = "ILLEGAL_STATE_TRANSITION"
    TERMINAL_STATE_IMMUTABLE = "TERMINAL_STATE_IMMUTABLE"
    CONCURRENCY_CONFLICT = "CONCURRENCY_CONFLICT"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    CSRF_REJECTED = "CSRF_REJECTED"
    ORIGIN_REJECTED = "ORIGIN_REJECTED"
    CONTENT_TYPE_REJECTED = "CONTENT_TYPE_REJECTED"
    BODY_TOO_LARGE = "BODY_TOO_LARGE"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    PATH_REJECTED = "PATH_REJECTED"
    WORKSPACE_TAMPERED = "WORKSPACE_TAMPERED"
    GOVERNANCE_NOT_READY = "GOVERNANCE_NOT_READY"


_HTTP_STATUS = {
    GovernanceErrorCode.CONCURRENCY_CONFLICT: 409,
    GovernanceErrorCode.REPLAY_DETECTED: 409,
    GovernanceErrorCode.STALE_DIAGNOSTIC_BINDING: 409,
    GovernanceErrorCode.UNKNOWN_DIAGNOSTIC: 404,
    GovernanceErrorCode.CSRF_REJECTED: 403,
    GovernanceErrorCode.ORIGIN_REJECTED: 403,
    GovernanceErrorCode.METHOD_NOT_ALLOWED: 405,
    GovernanceErrorCode.BODY_TOO_LARGE: 413,
}


class GovernanceError(ValueError):
    def __init__(self, code: GovernanceErrorCode, detail: str | None = None):
        self.code = code
        self.detail = detail or code.value
        super().__init__(self.detail)

    @property
    def http_status(self) -> int:
        return _HTTP_STATUS.get(self.code, 400)

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "detail": self.detail, "status": "FAILED"}
