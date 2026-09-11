"""Fail-closed errors for the derived diagnostics layer."""

from __future__ import annotations

from enum import Enum


class DiagnosticErrorCode(str, Enum):
    DIAGNOSTICS_NOT_READY = "DIAGNOSTICS_NOT_READY"
    AUTHORITY_MISMATCH = "AUTHORITY_MISMATCH"
    INVALID_DIAGNOSTIC_PACKAGE = "INVALID_DIAGNOSTIC_PACKAGE"
    READ_ONLY_POLICY_VIOLATION = "READ_ONLY_POLICY_VIOLATION"
    INVALID_REQUEST = "INVALID_REQUEST"


class DiagnosticError(ValueError):
    """A deterministic diagnostic operation failed closed."""

    def __init__(
        self,
        code: DiagnosticErrorCode,
        detail: str | None = None,
    ) -> None:
        self.code = code
        self.detail = detail or code.value
        super().__init__(self.detail)

    @property
    def http_status(self) -> int:
        return {
            DiagnosticErrorCode.DIAGNOSTICS_NOT_READY: 503,
            DiagnosticErrorCode.AUTHORITY_MISMATCH: 503,
            DiagnosticErrorCode.INVALID_DIAGNOSTIC_PACKAGE: 503,
            DiagnosticErrorCode.READ_ONLY_POLICY_VIOLATION: 405,
            DiagnosticErrorCode.INVALID_REQUEST: 400,
        }[self.code]

    def to_dict(self) -> dict[str, str]:
        return {
            "contract_version": "1.0",
            "code": self.code.value,
            "detail": self.detail,
        }
