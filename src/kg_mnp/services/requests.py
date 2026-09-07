"""Closed service DTOs, not a second Domain Contract catalogue."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

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


class ProposalRequest(RequestDTO):
    bundle_id: str = Field(pattern=r"^urn:kg-mnp:modeling-input-bundle:[a-f0-9]{64}$")
    providers: list[Literal["baseline-reuse-provider", "rule-mapping-provider"]] = Field(min_length=1, max_length=2)


class ReviewRequest(RequestDTO):
    review_id: str = Field(pattern=r"^urn:kg-mnp:ontology-review-queue:[a-f0-9]{64}$")


class ReviewActionRequest(ReviewRequest):
    candidate_id: str = Field(pattern=r"^urn:kg-mnp:ontology-candidate:[a-f0-9]{64}$")
    decision: Literal["ACCEPT", "REJECT", "DEFER", "COMMENT", "REQUEST_EVIDENCE"]
    rationale: str = Field(min_length=1, max_length=4000)
    expected_head: str | None = Field(pattern=r"^[a-f0-9]{64}$")


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
    pass


class ReleaseReviewRequest(RequestDTO):
    candidate_id: str = Field(pattern=r"^urn:kg-mnp:release-candidate:[a-f0-9]{64}$")
    decision: Literal["APPROVE", "REJECT"]
    rationale: str = Field(min_length=1, max_length=4000)


class ReleasePublishRequest(RequestDTO):
    candidate_id: str = Field(pattern=r"^urn:kg-mnp:release-candidate:[a-f0-9]{64}$")
    review_id: str = Field(pattern=r"^urn:kg-mnp:release-review:[a-f0-9]{64}$")
    expected_registry_head_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class MetadataRequest(PackageRequest):
    offset: int = Field(default=0, ge=0, le=1000000)
    limit: int = Field(default=100, ge=1, le=1000)


class ObjectRequest(MetadataRequest):
    class_iri: str | None = Field(default=None, max_length=500)
    instance_iri: str | None = Field(default=None, max_length=500)


REQUEST_MODELS = {
    "project.create": ProjectCreateRequest, "project.open": ProjectOpenRequest,
    "project.list": EmptyRequest, "project.validate": EmptyRequest, "project.lock": EmptyRequest,
    "domain-pack.discover": EmptyRequest, "domain-pack.inspect": PackInspectRequest,
    "job.get": JobRequest, "job.events": JobRequest, "operation.catalog": EmptyRequest,
    "registry.verify": EmptyRequest, "package.inspect": PackageRequest, "release.inspect": ReleaseRequest,
    "environment.inspect": EnvironmentRequest,
    "source.register": SourceRegisterRequest, "source.inspect": SourceRequest, "source.list": EmptyRequest,
    "source.verify": SourceRequest, "ingestion.plan": IngestionPlanRequest, "ingestion.run": IngestionRunRequest,
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
