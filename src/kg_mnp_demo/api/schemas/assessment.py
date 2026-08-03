"""Assessment request/response Pydantic models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kg_mnp_demo.api.schemas.common import (
    EligibilityDecisionCode,
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

    changes: dict[str, Any] = Field(default_factory=dict)


class WhatIfViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_payload: MNPCaseInput
    changes: dict[str, Any] = Field(default_factory=dict)


class PublicationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    publishable: bool
    status: PublicationStatus | str


class ValidationStepResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    label: str | None = None
    status: str | None = None
    conforms: bool | None = None
    detail: str | None = None


class ValidationsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    json_schema: ValidationStepResponse | dict[str, Any] | None = None
    input_graph: ValidationStepResponse | dict[str, Any] | None = None
    assessment_graph: ValidationStepResponse | dict[str, Any] | None = None


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    evidence_id: str | None = None
    evidence_iri: str | None = None
    evidence_type: str | None = None
    source_system: str | None = None
    generated_at: str | None = None
    valid_until: str | None = None
    status: str | None = None


class RuleResultResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    rule_id: str
    version: str | None = None
    status: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    selected_for_assessment_time: str | None = None


class BlockingReasonResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    reason_code: str
    rule_id: str | None = None
    rule_version: str | None = None
    regulatory_clause: str | None = None
    action_code: str | None = None
    evidence: EvidenceResponse | dict[str, Any] | None = None
    assessment_time: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None


class RemediationActionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    action_code: str | None = None
    iri: str | None = None


class AuthorizationCodeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str | None = None
    issued_at: str | None = None
    valid_until: str | None = None
    masked_value: str | None = None


class ProcessBlockingReason(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str | None = None
    message: str | None = None


class ProcessResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    current_step: str | None = None
    next_step: str | None = None
    can_advance: bool = False
    blocking_reasons: list[ProcessBlockingReason | dict[str, Any]] = Field(default_factory=list)
    authorization_code: AuthorizationCodeResponse | dict[str, Any] | None = None
    eligibility_decision: str | None = None


class TraceNodeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    label: str | None = None
    type: str | None = None


class TraceEdgeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str
    target: str
    predicate: str


class TraceGraphResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[TraceNodeResponse | dict[str, Any]] = Field(default_factory=list)
    edges: list[TraceEdgeResponse | dict[str, Any]] = Field(default_factory=list)


class InferenceResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    triples_before: int | None = None
    triples_after: int | None = None
    triples_added: int | None = None


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str
    execution_id: str
    case_id: str | None = None
    assessment_time: str | None = None
    decision: EligibilityDecisionCode | str | None = None
    publication: PublicationResponse | dict[str, Any]
    validations: ValidationsResponse | dict[str, Any]
    input_summary: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceResponse | dict[str, Any]] = Field(default_factory=list)
    rule_results: list[RuleResultResponse | dict[str, Any]] = Field(default_factory=list)
    blocking_reasons: list[BlockingReasonResponse | dict[str, Any]] = Field(
        default_factory=list
    )
    remediation_actions: list[RemediationActionResponse | dict[str, Any]] = Field(
        default_factory=list
    )
    process: ProcessResponse | dict[str, Any] = Field(default_factory=dict)
    trace_subgraph: TraceGraphResponse | dict[str, Any] = Field(default_factory=dict)
    inference: InferenceResponse | dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)


class AssessmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[dict[str, Any]] = Field(default_factory=list)


class AssessmentRecordResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    execution_id: str
    case_id: str
    assessment_time: str | None = None
    decision: str | None = None
    result: AssessmentResponse | dict[str, Any] | None = None
    input: dict[str, Any] | None = None


class ComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    decision_changed: bool | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    added_blocking_reasons: list[str] = Field(default_factory=list)
    removed_blocking_reasons: list[str] = Field(default_factory=list)
    changed_rule_versions: list[dict[str, Any]] = Field(default_factory=list)
    changed_evidence: dict[str, Any] | list[Any] = Field(default_factory=dict)
    rule_changes: list[dict[str, Any]] = Field(default_factory=list)


class WhatIfResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str | None = None
    baseline: dict[str, Any]
    scenario: dict[str, Any]
    changes: dict[str, Any] = Field(default_factory=dict)
    decision_changed: bool | None = None
    decision_change: dict[str, Any] | None = None
    rule_changes: list[dict[str, Any]] = Field(default_factory=list)
    reason_changes: dict[str, Any] = Field(default_factory=dict)
    evidence_changes: dict[str, Any] = Field(default_factory=dict)
    trace_changes: dict[str, Any] = Field(default_factory=dict)


class ArtifactsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str
    artifacts: dict[str, str] = Field(default_factory=dict)
