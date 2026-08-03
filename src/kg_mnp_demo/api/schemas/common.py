"""Shared enums and error response models for the API."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EligibilityDecisionCode(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"
    CONDITIONAL = "CONDITIONAL"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class PublicationStatus(str, Enum):
    PUBLISHABLE = "PUBLISHABLE"
    NOT_PUBLISHABLE = "NOT_PUBLISHABLE"


class EvidenceStatus(str, Enum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    UNKNOWN = "UNKNOWN"


class AuthorizationCodeStatus(str, Enum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    MISSING = "MISSING"
    USED = "USED"
    REVOKED = "REVOKED"


class ProcessStepCode(str, Enum):
    ELIGIBILITY_CHECK = "ELIGIBILITY_CHECK"
    AUTHORIZATION_CODE_REQUEST = "AUTHORIZATION_CODE_REQUEST"
    PORT_IN_SUBMISSION = "PORT_IN_SUBMISSION"
    PORTING_EXECUTION = "PORTING_EXECUTION"
    PORTING_CONFIRMATION = "PORTING_CONFIRMATION"


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: list[Any] = Field(default_factory=list)
    retryable: bool = False


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


class ItemList(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[Any] = Field(default_factory=list)


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    time: str


class ReadyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    sqlite: bool
    neo4j_required: bool = False


class MetaResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    api_version: str
    schema_version: str
    project_root_name: str | None = None
    cors_note: str | None = None
    max_request_bytes_env: str | None = None
    backend: str | None = None
    neo4j_required: bool = False


class CaseCatalogItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    case_id: str
    ttl_file: str | None = None
    json_file: str | None = None
    expected_decision: str | None = None
    scenario: str | None = None


class CaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CaseCatalogItem | dict[str, Any]] = Field(default_factory=list)


class CaseDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    case_id: str
    ttl_file: str | None = None
    json_file: str | None = None
    input: dict[str, Any] | None = None
    expected_decision: str | None = None
    scenario: str | None = None


class CaseHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    case_id: str
    items: list[Any] = Field(default_factory=list)


ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}
