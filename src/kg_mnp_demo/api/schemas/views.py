from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from kg_mnp_demo.api.schemas.common import JsonValue


class CaseCountStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = 0
    eligible: int = 0
    blocked: int = 0
    manual_review: int = 0


class OntologyDashboardStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    model_config = ConfigDict(extra="forbid")

    project: dict[str, JsonValue]
    capabilities: list[str] = Field(default_factory=list)
    ontology: OntologyDashboardStats
    example_cases: CaseCountStats
    executions: CaseCountStats
    latest_case_states: CaseCountStats
    cases: CaseCountStats | None = None
    pipeline_steps: list[dict[str, JsonValue]] = Field(default_factory=list)
    example_case_ids: list[str] = Field(default_factory=list)


class AssessmentViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    header: dict[str, JsonValue] = Field(default_factory=dict)
    decision_card: dict[str, JsonValue] = Field(default_factory=dict)
    input_summary: dict[str, JsonValue] = Field(default_factory=dict)
    validation_steps: list[dict[str, JsonValue]] = Field(default_factory=list)
    evidence_table: list[dict[str, JsonValue]] = Field(default_factory=list)
    rule_execution_table: list[dict[str, JsonValue]] = Field(default_factory=list)
    blocking_reason_cards: list[dict[str, JsonValue]] = Field(default_factory=list)
    remediation_actions: list[dict[str, JsonValue]] = Field(default_factory=list)
    process_status: dict[str, JsonValue] = Field(default_factory=dict)
    trace_graph: dict[str, JsonValue] = Field(default_factory=dict)
    timeline: list[dict[str, JsonValue]] = Field(default_factory=list)
    artifacts: list[dict[str, JsonValue]] = Field(default_factory=list)
    technical_details: dict[str, JsonValue] = Field(default_factory=dict)


class CaseViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case: dict[str, JsonValue]
    latest_assessment: AssessmentViewResponse | None = None


class CaseSummaryViewItem(BaseModel):
    """One row in the aggregated case catalog view.

    The catalog deliberately contains only execution metadata.  Full case
    history and assessment views remain available from their dedicated
    endpoints.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    scenario: str | None = None
    expected_decision: str | None = None
    ttl_file: str | None = None
    json_file: str | None = None
    latest_execution_id: str | None = None
    latest_assessment_time: str | None = None
    latest_decision: str | None = None
    publication_status: str | None = None
    execution_count: int = 0
    has_history: bool = False


class CaseListViewResponse(BaseModel):
    """Aggregated case catalog and latest execution summaries."""

    model_config = ConfigDict(extra="forbid")

    items: list[CaseSummaryViewItem] = Field(default_factory=list)


class ExampleItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    runnable: bool = True
    input_format: str = "json"
    expected_decision: str | None = None
    scenario: str | None = None
    json_file: str | None = None
    ttl_file: str | None = None


class ExampleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ExampleItem] = Field(default_factory=list)


class ExampleDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    runnable: bool = True
    input_format: str = "json"
    expected_decision: str | None = None
    scenario: str | None = None
    input: dict[str, JsonValue] | None = None
    json_file: str | None = None
    ttl_file: str | None = None


class OntologyKeyPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_class: str
    predicate: str
    target_class: str
    exists_in_rdf: bool = True


class OntologyViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modules: list[dict[str, JsonValue]] = Field(default_factory=list)
    graph: dict[str, JsonValue] = Field(default_factory=dict)
    key_paths: list[OntologyKeyPath] = Field(default_factory=list)
    stats: dict[str, JsonValue] = Field(default_factory=dict)


class TraceViewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str | None = None
    execution_id: str | None = None
    graph: dict[str, JsonValue] = Field(default_factory=dict)
    node_count: int = 0
    edge_count: int = 0


class TimelineStepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    status: str | None = None


class TimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str
    timeline: list[TimelineStepResponse] = Field(default_factory=list)
