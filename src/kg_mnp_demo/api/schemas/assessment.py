"""Assessment request/response Pydantic models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kg_mnp_demo.api.schemas.common import (
    EligibilityDecisionCode,
    JsonValue,
    PublicationStatus,
)
from kg_mnp_demo.api.schemas.input import MNPCaseInput


class AssessmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: MNPCaseInput
    persist: bool = True
    force_recompute: bool = False


class WhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: dict[str, JsonValue] = Field(default_factory=dict)


class WhatIfViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_payload: MNPCaseInput
    changes: dict[str, JsonValue] = Field(default_factory=dict)


class PublicationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publishable: bool
    status: PublicationStatus


class ValidationStepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    status: str | None = None
    conforms: bool | None = None
    detail: str | None = None


class ValidationsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    json_schema: ValidationStepResponse | None = None
    input_graph: ValidationStepResponse | None = None
    assessment_graph: ValidationStepResponse | None = None


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    evidence_id: str | None = None
    evidence_iri: str | None = None
    evidence_type: str | None = None
    source_system: str | None = None
    generated_at: datetime | str | None = None
    valid_until: datetime | str | None = None
    status: str | None = None


class RuleResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    version: str | None = None
    status: str | None = None
    effective_from: datetime | str | None = None
    effective_to: datetime | str | None = None
    selected_for_assessment_time: datetime | str | None = None


class BlockingReasonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str
    rule_id: str | None = None
    rule_version: str | None = None
    regulatory_clause: str | None = None
    action_code: str | None = None
    evidence: EvidenceResponse | None = None
    assessment_time: datetime | str | None = None
    effective_from: datetime | str | None = None
    effective_to: datetime | str | None = None


class RemediationActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_code: str | None = None
    iri: str | None = None


class AuthorizationCodeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    issued_at: datetime | str | None = None
    valid_until: datetime | str | None = None
    masked_value: str | None = None


class ProcessBlockingReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = None
    message: str | None = None


class ProcessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_step: str | None = None
    next_step: str | None = None
    can_advance: bool = False
    blocking_reasons: list[ProcessBlockingReason] = Field(default_factory=list)
    authorization_code: AuthorizationCodeResponse | None = None
    eligibility_decision: str | None = None


class TraceNodeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    local_id: str | None = None
    label: str | None = None
    type: str | None = None


class TraceEdgeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str
    target: str
    predicate: str


class TraceGraphResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[TraceNodeResponse] = Field(default_factory=list)
    edges: list[TraceEdgeResponse] = Field(default_factory=list)
    case_id: str | None = None
    root: str | None = None
    root_local: str | None = None
    query_file: str | None = None


class InferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triples_before: int | None = None
    triples_after: int | None = None
    triples_added: int | None = None


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    execution_id: str
    case_id: str | None = None
    assessment_time: datetime | str | None = None
    decision: EligibilityDecisionCode | None = None
    publication: PublicationResponse
    validations: ValidationsResponse
    input_summary: dict[str, JsonValue] = Field(default_factory=dict)
    evidence: list[EvidenceResponse] = Field(default_factory=list)
    rule_results: list[RuleResultResponse] = Field(default_factory=list)
    blocking_reasons: list[BlockingReasonResponse] = Field(default_factory=list)
    remediation_actions: list[RemediationActionResponse] = Field(default_factory=list)
    process: ProcessResponse = Field(default_factory=ProcessResponse)
    trace_subgraph: TraceGraphResponse = Field(default_factory=TraceGraphResponse)
    inference: InferenceResponse = Field(default_factory=InferenceResponse)
    warnings: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)


class AssessmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[dict[str, JsonValue]] = Field(default_factory=list)


class AssessmentRecordResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    execution_id: str
    case_id: str
    assessment_time: datetime | str | None = None
    decision: str | None = None
    result: AssessmentResponse | None = None
    input: dict[str, JsonValue] | None = None


class ComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_changed: bool | None = None
    before: dict[str, JsonValue] | None = None
    after: dict[str, JsonValue] | None = None
    added_blocking_reasons: list[str] = Field(default_factory=list)
    removed_blocking_reasons: list[str] = Field(default_factory=list)
    changed_rule_versions: list[dict[str, JsonValue]] = Field(default_factory=list)
    changed_evidence: dict[str, JsonValue] = Field(default_factory=dict)
    rule_changes: list[dict[str, JsonValue]] = Field(default_factory=list)


class DecisionChangeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    changed: bool
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None


class WhatIfResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str | None = None
    baseline: dict[str, JsonValue]
    scenario: dict[str, JsonValue]
    changes: dict[str, JsonValue] = Field(default_factory=dict)
    decision_changed: bool | None = None
    decision_change: dict[str, JsonValue] | None = None
    rule_changes: list[dict[str, JsonValue]] = Field(default_factory=list)
    reason_changes: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_changes: dict[str, JsonValue] = Field(default_factory=dict)
    trace_changes: dict[str, JsonValue] = Field(default_factory=dict)


class ArtifactsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str
    artifacts: dict[str, str] = Field(default_factory=dict)
