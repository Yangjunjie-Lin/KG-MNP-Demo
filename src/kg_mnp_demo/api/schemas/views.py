from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CaseCountStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = 0
    eligible: int = 0
    blocked: int = 0
    manual_review: int = 0


class OntologyDashboardStats(BaseModel):
    model_config = ConfigDict(extra="allow")

    module_count: int | None = None
    class_count: int | None = None
    object_property_count: int | None = None
    data_property_count: int | None = None
    shape_count: int | None = None
    node_shape_count: int | None = None
    property_shape_count: int | None = None
    rule_count: int | None = None
    competency_question_count: int | None = None


class DashboardViewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    project: dict[str, Any]
    capabilities: list[str] = Field(default_factory=list)
    ontology: OntologyDashboardStats | dict[str, Any]
    example_cases: CaseCountStats | dict[str, Any]
    executions: CaseCountStats | dict[str, Any]
    latest_case_states: CaseCountStats | dict[str, Any]
    cases: CaseCountStats | dict[str, Any] | None = None
    pipeline_steps: list[dict[str, Any]] = Field(default_factory=list)
    example_case_ids: list[str] = Field(default_factory=list)


class AssessmentViewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    header: dict[str, Any] = Field(default_factory=dict)
    decision_card: dict[str, Any] = Field(default_factory=dict)
    input_summary: dict[str, Any] = Field(default_factory=dict)
    validation_steps: list[dict[str, Any]] = Field(default_factory=list)
    evidence_table: list[dict[str, Any]] = Field(default_factory=list)
    rule_execution_table: list[dict[str, Any]] = Field(default_factory=list)
    blocking_reason_cards: list[dict[str, Any]] = Field(default_factory=list)
    remediation_actions: list[dict[str, Any]] = Field(default_factory=list)
    process_status: dict[str, Any] = Field(default_factory=dict)
    trace_graph: dict[str, Any] = Field(default_factory=dict)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    technical_details: dict[str, Any] = Field(default_factory=dict)


class CaseViewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    case: dict[str, Any]
    latest_assessment: AssessmentViewResponse | dict[str, Any] | None = None


class ExampleItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    case_id: str
    runnable: bool = True
    input_format: str = "json"
    expected_decision: str | None = None
    scenario: str | None = None
    json_file: str | None = None
    ttl_file: str | None = None


class ExampleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ExampleItem | dict[str, Any]] = Field(default_factory=list)


class ExampleDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    case_id: str
    runnable: bool = True
    input_format: str = "json"
    expected_decision: str | None = None
    scenario: str | None = None
    input: dict[str, Any] | None = None
    ttl_file: str | None = None
