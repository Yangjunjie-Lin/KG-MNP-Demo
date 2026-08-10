"""Fail-closed Phase 02 error contract."""

from __future__ import annotations

from enum import Enum


class WorkbenchErrorCode(str, Enum):
    WORKBENCH_NOT_READY = "WORKBENCH_NOT_READY"
    INVALID_REQUEST = "INVALID_REQUEST"
    READ_ONLY_POLICY_VIOLATION = "READ_ONLY_POLICY_VIOLATION"
    RELAY_ROUTE_FORBIDDEN = "RELAY_ROUTE_FORBIDDEN"
    PHASE01_UNAVAILABLE = "PHASE01_UNAVAILABLE"
    PHASE01_RESPONSE_INVALID = "PHASE01_RESPONSE_INVALID"
    PACKAGE_INVALID = "PACKAGE_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_HTTP_STATUS = {
    WorkbenchErrorCode.WORKBENCH_NOT_READY: 503,
    WorkbenchErrorCode.INVALID_REQUEST: 422,
    WorkbenchErrorCode.READ_ONLY_POLICY_VIOLATION: 405,
    WorkbenchErrorCode.RELAY_ROUTE_FORBIDDEN: 404,
    WorkbenchErrorCode.PHASE01_UNAVAILABLE: 503,
    WorkbenchErrorCode.PHASE01_RESPONSE_INVALID: 502,
    WorkbenchErrorCode.PACKAGE_INVALID: 500,
    WorkbenchErrorCode.INTERNAL_ERROR: 500,
}


class WorkbenchError(RuntimeError):
    """An intentionally non-sensitive workbench failure."""

    def __init__(
        self,
        code: WorkbenchErrorCode,
        message: str | None = None,
    ) -> None:
        super().__init__(message or code.value)
        self.code = code
        self.http_status = _HTTP_STATUS[code]

    def to_dict(self) -> dict[str, object]:
        return {
            "error": {
                "code": self.code.value,
                "message": self.code.value,
            }
        }
