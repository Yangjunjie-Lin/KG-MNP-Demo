from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuleVersionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    rule_id: str
    version: str
    name: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    reason_code: str | None = None
    action_code: str | None = None
    regulatory_clause: str | None = None


class RuleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RuleVersionResponse | dict[str, Any]] = Field(default_factory=list)


class RuleDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    versions: list[dict[str, Any]] = Field(default_factory=list)


class AffectedAssessmentItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    execution_id: str
    case_id: str
    assessment_time: str | None = None
    requires_reassessment: bool = True
    rule_id: str | None = None
    old_version: str | None = None
    new_version: str | None = None


class AffectedAssessmentsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    old_version: str
    new_version: str | None = None
    items: list[AffectedAssessmentItem | dict[str, Any]] = Field(default_factory=list)
