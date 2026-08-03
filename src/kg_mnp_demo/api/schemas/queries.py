from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CompetencyQuestionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title_zh: str | None = None
    question: str | None = None
    description: str | None = None
    required_inputs: list[str] = Field(default_factory=list)
    return_fields: list[str] = Field(default_factory=list)
    query_file: str | None = None
    supported_backends: list[str] = Field(default_factory=list)
    example_case: str | None = None


class CompetencyQuestionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CompetencyQuestionResponse | dict[str, Any]] = Field(default_factory=list)


class CompetencyExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str


class CompetencyQuestionExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    question_id: str
    question: str | None = None
    title_zh: str | None = None
    case_id: str
    status: str
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
