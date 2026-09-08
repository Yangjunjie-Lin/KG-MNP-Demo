"""Closed service DTOs, not a second Domain Contract catalogue."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kg_mnp.modeling.control_plane.providers.record_profile import MixedRecordMapping

from .errors import ServiceBoundaryError


class RequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyRequest(RequestDTO):
    pass


class ProjectCreateRequest(RequestDTO):
    name: str = Field(min_length=1, max_length=200)
    domain_pack: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    domain_pack_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ProjectOpenRequest(RequestDTO):
    project_id: str | None = None


class PackInspectRequest(RequestDTO):
    pack_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    pack_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")


class JobRequest(RequestDTO):
    job_id: str = Field(pattern=r"^job_[a-f0-9]{32}$")


class PackageRequest(RequestDTO):
    package_id: str = Field(min_length=1, max_length=200)


class ReleaseRequest(RequestDTO):
    release_id: str = Field(min_length=1, max_length=200)


class EnvironmentRequest(RequestDTO):
    environment_id: str = Field(min_length=1, max_length=200)


class SourceRegisterRequest(RequestDTO):
    upload_id: str = Field(pattern=r"^[a-f0-9]{64}$")


class SourceRequest(RequestDTO):
    source_id: str = Field(pattern=r"^urn:kg-mnp:source:[a-f0-9]{64}$")


class SourceBatchRequest(RequestDTO):
    source_ids:list[str]=Field(min_length=1,max_length=100)


class IngestionPlanRequest(RequestDTO):
    batch_id: str = Field(pattern=r"^urn:kg-mnp:source-batch:[a-f0-9]{64}$")


class IngestionRunRequest(RequestDTO):
    plan_id: str = Field(pattern=r"^urn:kg-mnp:ingestion-plan:[a-f0-9]{64}$")


class IngestionInspectRequest(RequestDTO):
    run_id: str = Field(pattern=r"^urn:kg-mnp:ingestion-run:[a-f0-9]{64}$")
    item_id: str | None = Field(default=None, pattern=r"^urn:kg-mnp:kg-ir-item:[a-f0-9]{64}$")


class ScopeRequest(RequestDTO):
    run_id: str = Field(pattern=r"^urn:kg-mnp:ingestion-run:[a-f0-9]{64}$")
    description: str = Field(min_length=1, max_length=4000)
    object_families: list[str] = Field(min_length=1, max_length=100)
    in_scope: list[str] = Field(min_length=1, max_length=100)
    out_of_scope: list[str] = Field(default_factory=list, max_length=100)
    namespace: str = Field(min_length=1, max_length=300)
    intent: Literal["CREATE_NEW_ONTOLOGY", "EXTEND_BASELINE", "ALIGN_TO_BASELINE", "INSTANCE_POPULATION", "MAPPING_ONLY", "MIXED_MODELING"] = "MIXED_MODELING"


class ScopeApprovalRequest(RequestDTO):
    scope_id: str = Field(pattern=r"^urn:kg-mnp:ontology-scope:[a-f0-9]{64}$")
    expected_approval_id: str | None = Field(default=None, pattern=r"^urn:kg-mnp:ontology-scope-approval:[a-f0-9]{64}$")
    rationale: str = Field(min_length=1, max_length=4000)
    decision: Literal["APPROVE", "REJECT", "REQUEST_CHANGES"] = "APPROVE"


class QuestionDraft(RequestDTO):
    question_text: str = Field(min_length=1, max_length=4000)
    purpose: str = Field(min_length=1, max_length=4000)
    required_concepts: list[str] = Field(default_factory=list, max_length=100)
    expected_answer_shape: Literal["ENTITY_LIST", "RELATION_LIST", "BOOLEAN", "AGGREGATE", "VALUE", "GRAPH", "OTHER"] = "ENTITY_LIST"


class ModelingPrepareRequest(RequestDTO):
    scope_id: str = Field(pattern=r"^urn:kg-mnp:ontology-scope:[a-f0-9]{64}$")
    approval_id: str = Field(pattern=r"^urn:kg-mnp:ontology-scope-approval:[a-f0-9]{64}$")
    questions: list[QuestionDraft] = Field(min_length=1, max_length=100)


class RecordReferenceRequest(RequestDTO):
    field:str=Field(min_length=1,max_length=100)
    target_table:str=Field(pattern=r"^[a-z][a-z0-9-]{0,50}$")
    predicate_iri:str=Field(min_length=1,max_length=500)


class RecordTableRequest(RequestDTO):
    table_id:str=Field(pattern=r"^[a-z][a-z0-9-]{0,50}$")
    source_name:str=Field(min_length=1,max_length=200)
    class_iri:str=Field(min_length=1,max_length=500)
    id_field:str=Field(min_length=1,max_length=100)
    literals:dict[str,str]=Field(max_length=100)
    references:list[RecordReferenceRequest]=Field(default_factory=list,max_length=100)


class RecordMappingRequest(RequestDTO):
    profile:Literal["evidence-record-mapping-v1"]
    tables:list[RecordTableRequest]=Field(min_length=1,max_length=20)


class ProposalRequest(RequestDTO):
    bundle_id: str = Field(pattern=r"^urn:kg-mnp:modeling-input-bundle:[a-f0-9]{64}$")
    providers: list[Literal["baseline-reuse-provider", "rule-mapping-provider","manual-candidate-provider","recorded-model-output-provider"]] = Field(min_length=1, max_length=4)
    record_mapping:RecordMappingRequest|MixedRecordMapping|None=None
    recorded_response_source_id:str|None=Field(default=None,pattern=r"^urn:kg-mnp:source:[a-f0-9]{64}$")
    recorded_prompt_source_id:str|None=Field(default=None,pattern=r"^urn:kg-mnp:source:[a-f0-9]{64}$")
    recorded_model_id:str|None=Field(default=None,max_length=200)
    recorded_model_revision:str|None=Field(default=None,max_length=200)


class ReviewRequest(RequestDTO):
    review_id: str = Field(pattern=r"^urn:kg-mnp:ontology-review-queue:[a-f0-9]{64}$")


class LiteralEdit(RequestDTO):
    lexical_value:str=Field(max_length=10000)
    datatype_iri:str|None=None
    language:str|None=None


class CandidateBodyEdit(RequestDTO):
    label:str|None=None
    subject_iri:str|None=None
    predicate_iri:str|None=None
    object_iri:str|None=None
    target_iri:str|None=None
    source_field:str|None=None
    literal:LiteralEdit|None=None


class ReviewActionRequest(ReviewRequest):
    candidate_id: str|None = Field(default=None,pattern=r"^urn:kg-mnp:ontology-candidate:[a-f0-9]{64}$")
    issue_id:str|None=Field(default=None,pattern=r"^urn:kg-mnp:[a-z0-9-]+:[a-f0-9]{64}$")
    decision: Literal["ACCEPT", "REJECT", "DEFER", "COMMENT", "REQUEST_EVIDENCE","MODIFY_AND_ACCEPT","RESOLVE_CONFLICT"]
    rationale: str = Field(min_length=1, max_length=4000)
    expected_head: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    body_edits:CandidateBodyEdit|None=None


class CQOracleRequest(RequestDTO):
    question_id: str = Field(pattern=r"^urn:kg-mnp:competency-question:[a-f0-9]{64}$")
    query_asset_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,150}$")
    min_rows: int = Field(ge=1, le=100000)
    required_bindings: list[str] = Field(min_length=1, max_length=100)


class CompilePlanRequest(RequestDTO):
    confirmed_package_id: str = Field(pattern=r"^urn:kg-mnp:[a-z0-9-]+:[a-f0-9]{64}$")
    package_name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,100}$")
    package_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    ontology_iri: str = Field(min_length=1, max_length=500)
    version_iri: str = Field(min_length=1, max_length=500)
    oracles: list[CQOracleRequest] = Field(min_length=1, max_length=100)


class CompileBuildRequest(RequestDTO):
    plan_id: str = Field(pattern=r"^urn:kg-mnp:[a-z0-9-]+:[a-f0-9]{64}$")


class ReleaseCandidateRequest(PackageRequest):
    change_evaluation_id: str | None = Field(default=None,pattern=r"^urn:kg-mnp:[a-z0-9-]+:[a-f0-9]{64}$")


class ReleaseReviewRequest(RequestDTO):
    candidate_id: str = Field(pattern=r"^urn:kg-mnp:release-candidate:[a-f0-9]{64}$")
    decision: Literal["APPROVE", "REJECT"]
    rationale: str = Field(min_length=1, max_length=4000)


class ReleasePublishRequest(RequestDTO):
    candidate_id: str = Field(pattern=r"^urn:kg-mnp:release-candidate:[a-f0-9]{64}$")
    review_id: str = Field(pattern=r"^urn:kg-mnp:release-review:[a-f0-9]{64}$")
    expected_registry_head_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class JobRecoveryRequest(RequestDTO):
    mode: Literal["RECOVER_COMMITTED", "RETRY_LOCAL"]
    expected_attempt: int = Field(ge=1)


class MetadataRequest(PackageRequest):
    release_id: str | None = Field(default=None, pattern=r"^urn:kg-mnp:release:[a-f0-9]{64}$")
    offset: int = Field(default=0, ge=0, le=1000000)
    limit: int = Field(default=100, ge=1, le=1000)


class ObjectRequest(MetadataRequest):
    class_iri: str | None = Field(default=None, max_length=500)
    instance_iri: str | None = Field(default=None, max_length=500)


class ObjectTraceRequest(PackageRequest):
    instance_iri:str=Field(min_length=1,max_length=500)


class DiffRequest(RequestDTO):
    base_package_id: str = Field(pattern=r"^urn:kg-mnp:ontology-package:[a-f0-9]{64}$")
    candidate_package_id: str = Field(pattern=r"^urn:kg-mnp:ontology-package:[a-f0-9]{64}$")


class DiffReferenceRequest(RequestDTO):
    diff_id: str = Field(pattern=r"^urn:kg-mnp:semantic-diff-report:[a-f0-9]{64}$")


class RegressionRequest(DiffReferenceRequest):
    impact_id: str = Field(pattern=r"^urn:kg-mnp:impact-analysis-report:[a-f0-9]{64}$")


class ChangeEvaluationRequest(RegressionRequest):
    regression_report_id: str = Field(pattern=r"^urn:kg-mnp:regression-test-report:[a-f0-9]{64}$")
    rationale: str = Field(min_length=1,max_length=4000)


class EnvironmentCreateRequest(RequestDTO):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,80}$")


class EnvironmentProposalRequest(RequestDTO):
    environment_id: str = Field(pattern=r"^urn:kg-mnp:environment-manifest:[a-f0-9]{64}$")
    release_id: str = Field(pattern=r"^urn:kg-mnp:release:[a-f0-9]{64}$")
    rationale: str = Field(min_length=1,max_length=4000)
    kind: Literal["ACTIVATE","ROLLBACK"]


class EnvironmentReviewRequest(RequestDTO):
    proposal_id: str = Field(pattern=r"^urn:kg-mnp:activation-proposal:[a-f0-9]{64}$")
    decision: Literal["APPROVE","REJECT"]
    rationale: str = Field(min_length=1,max_length=4000)
    breaking_change_acknowledged: bool


class EnvironmentExecutionRequest(RequestDTO):
    proposal_id: str = Field(pattern=r"^urn:kg-mnp:activation-proposal:[a-f0-9]{64}$")
    decision_id: str = Field(pattern=r"^urn:kg-mnp:activation-review-decision:[a-f0-9]{64}$")
    expected_generation: int = Field(ge=0)
    expected_pointer_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_registry_head_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class IntegrationPlanRequest(RequestDTO):
    release_id:str=Field(pattern=r"^urn:kg-mnp:release:[a-f0-9]{64}$")
    target_id:Literal["local-graphdb"]


class IntegrationReviewRequest(RequestDTO):
    plan_id:str=Field(pattern=r"^plan_[a-f0-9]{64}$")
    rationale:str=Field(min_length=1,max_length=4000)


class IntegrationExecuteRequest(RequestDTO):
    plan_id:str=Field(pattern=r"^plan_[a-f0-9]{64}$")
    approval_id:str=Field(pattern=r"^approval_[a-f0-9]{64}$")


class WorkflowRequest(RequestDTO):
    release_id:str=Field(pattern=r"^urn:kg-mnp:release:[a-f0-9]{64}$")
    action_id:Literal["request-source-review"]
    note:str=Field(min_length=1,max_length=4000)


class FeedbackRequest(PackageRequest):
    observations:list[str]=Field(min_length=1,max_length=100)
    severity:Literal["INFO","WARNING","ERROR","CRITICAL"]="INFO"


class ConsumerAssertionRequest(RequestDTO):
    assertion_type: Literal["BOOLEAN_EQUALS", "MIN_ROW_COUNT", "MAX_ROW_COUNT", "REQUIRED_BINDINGS", "REQUIRED_IRIS", "RESULT_SEMANTIC_HASH", "GRAPH_PATTERN_PRESENT"]
    boolean_value: bool | None = None
    integer_value: int | None = Field(default=None, ge=0, le=100000)
    string_values: list[str] = Field(default_factory=list, max_length=1000)
    semantic_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class ConsumerQueryLimits(RequestDTO):
    max_query_characters: int = Field(default=100000, ge=1, le=100000)
    max_query_results: int = Field(default=1000, ge=1, le=100000)
    max_query_seconds: int = Field(default=30, ge=1, le=60)
    max_query_path_depth: int = Field(default=8, ge=1, le=8)


class ConsumerQueryRequest(RequestDTO):
    query_type: Literal["ASK", "SELECT", "CONSTRUCT"]
    query_text: str = Field(min_length=1, max_length=100000)
    target_graph_roles: list[str] = Field(min_length=1, max_length=20)
    assertions: list[ConsumerAssertionRequest] = Field(min_length=1, max_length=100)
    resource_limits: ConsumerQueryLimits = Field(default_factory=ConsumerQueryLimits)


class ConsumerRequest(PackageRequest):
    name:str=Field(min_length=1,max_length=100)
    required_term_iris:list[str]=Field(default_factory=list,max_length=1000)
    query_contracts: list[ConsumerQueryRequest] = Field(default_factory=list, max_length=100)


REQUEST_MODELS = {
    "project.create": ProjectCreateRequest, "project.open": ProjectOpenRequest,
    "project.list": EmptyRequest, "project.validate": EmptyRequest, "project.lock": EmptyRequest,
    "domain-pack.discover": EmptyRequest, "domain-pack.inspect": PackInspectRequest,
    "job.get": JobRequest, "job.events": JobRequest, "operation.catalog": EmptyRequest,
    "registry.verify": EmptyRequest, "package.inspect": PackageRequest, "release.inspect": ReleaseRequest,
    "environment.inspect": EnvironmentRequest,
    "source.register": SourceRegisterRequest, "source.inspect": SourceRequest, "source.list": EmptyRequest,
    "source.verify": SourceRequest, "ingestion.plan": IngestionPlanRequest, "ingestion.run": IngestionRunRequest,
    "source.batch":SourceBatchRequest,
    "ingestion.inspect": IngestionInspectRequest, "ingestion.trace": IngestionInspectRequest,
    "evidence.list": IngestionInspectRequest, "kgir.inspect": IngestionInspectRequest, "kgir.validate": IngestionInspectRequest,
    "modeling.scope": ScopeRequest, "modeling.scope.approve": ScopeApprovalRequest,
    "modeling.prepare": ModelingPrepareRequest, "modeling.cq": ModelingPrepareRequest,
    "modeling.baseline": ModelingPrepareRequest, "modeling.alignment": ModelingPrepareRequest,
    "modeling.candidate": ProposalRequest, "modeling.proposal": ProposalRequest,
    "review.action": ReviewActionRequest, "review.replay": ReviewRequest, "review.finalize": ReviewRequest,
    "compile.plan": CompilePlanRequest, "compile.build": CompileBuildRequest,
    "compile.reproduce": CompileBuildRequest, "compile.validate": PackageRequest,
    "package.verify": PackageRequest, "package.export": PackageRequest,
    "registry.import": PackageRequest, "release.candidate": ReleaseCandidateRequest,
    "release.review": ReleaseReviewRequest, "release.publish": ReleasePublishRequest,
    "oms.metadata": MetadataRequest, "ods.query": ObjectRequest,
    "object.trace":ObjectTraceRequest,
    "change.diff":DiffRequest,"change.impact":DiffReferenceRequest,"change.regression":RegressionRequest,"change.evaluate":ChangeEvaluationRequest,
    "environment.create":EnvironmentCreateRequest,"environment.propose":EnvironmentProposalRequest,"environment.review":EnvironmentReviewRequest,
    "environment.activate":EnvironmentExecutionRequest,"environment.rollback":EnvironmentExecutionRequest,
    "visualization.export":PackageRequest,"integration.plan":IntegrationPlanRequest,"integration.review":IntegrationReviewRequest,
    "integration.execute":IntegrationExecuteRequest,"integration.verify":IntegrationExecuteRequest,"workflow.enqueue":WorkflowRequest,
    "feedback.add":FeedbackRequest,"consumer.register":ConsumerRequest,
}


def validate_parameters(request):
    model = REQUEST_MODELS.get(request.operation_id)
    if model is None:
        raise ServiceBoundaryError("OPERATION_BLOCKED", "typed service request is not implemented", status_code=501)
    try:
        model.model_validate(request.parameters)
    except ValidationError as exc:
        # Avoid Pydantic's input echo, which may contain credentials or paths.
        raise ServiceBoundaryError("REQUEST_INVALID", "request does not match the operation contract", status_code=422) from exc
