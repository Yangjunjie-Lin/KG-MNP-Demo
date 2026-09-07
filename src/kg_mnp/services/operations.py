"""One explicit operation catalogue; no import/getattr or command dispatch."""
from __future__ import annotations

from dataclasses import replace

from .models import OperationDefinition

_READ = ("project:read",)
_WRITE = ("project:write",)


def build_operation_catalog() -> dict[str, OperationDefinition]:
    definitions: list[OperationDefinition] = [
        OperationDefinition("project.create", "ProjectCreateRequest", "ProjectHandle", _WRITE, False, "INLINE", "WRITE", "OPTIONAL"),
        OperationDefinition("project.open", "ProjectOpenRequest", "ProjectHandle", _READ, False),
        OperationDefinition("project.list", "ProjectListRequest", "ProjectListResult", _READ, False),
        OperationDefinition("project.validate", "ProjectHandle", "ProjectValidationResult", _READ),
        OperationDefinition("project.lock", "ProjectLockRequest", "ProjectHandle", _WRITE, True, "INLINE", "WRITE", "REQUIRED"),
        OperationDefinition("domain-pack.discover", "DomainPackRequest", "DomainPackList", _READ, False),
        OperationDefinition("domain-pack.inspect", "DomainPackRequest", "DomainPackSnapshot", _READ, False),
        OperationDefinition("source.register", "SourceRegisterRequest", "Artifact", ("source:write",), True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("source.inspect", "ArtifactRequest", "Artifact", ("source:read",), True),
        OperationDefinition("source.list", "EmptyRequest", "SourceList", ("source:read",), True),
        OperationDefinition("source.verify", "SourceRequest", "SourceAsset", ("source:read",), True),
        OperationDefinition("evidence.list", "IngestionInspectRequest", "EvidenceList", ("source:read",), True),
        OperationDefinition("kgir.inspect", "IngestionInspectRequest", "KGIRDataset", ("source:read",), True),
        OperationDefinition("kgir.validate", "IngestionInspectRequest", "KGIRDataset", ("source:read",), True),
        OperationDefinition("ingestion.plan", "IngestionPlanRequest", "IngestionPlan", _WRITE, True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("ingestion.run", "IngestionRunRequest", "IngestionRun", _WRITE, True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("ingestion.inspect", "ArtifactRequest", "IngestionRun", ("source:read",)),
        OperationDefinition("ingestion.trace", "ArtifactRequest", "Trace", ("source:read",)),
        OperationDefinition("modeling.scope", "ModelingScopeRequest", "Artifact", ("model:propose",), True, "INLINE", "WRITE", "REQUIRED"),
        OperationDefinition("modeling.scope.approve", "ReviewDecisionRequest", "Artifact", ("scope:approve",), True, "INLINE", "WRITE", "REQUIRED"),
        OperationDefinition("modeling.candidate", "ModelingCandidateRequest", "Artifact", ("model:propose",), True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("modeling.cq", "CQRequest", "CQResult", ("model:propose",), True, "JOB", "READ", "REQUIRED"),
        OperationDefinition("modeling.baseline", "BaselineRequest", "Artifact", ("model:propose",), True, "INLINE", "WRITE", "REQUIRED"),
        OperationDefinition("modeling.alignment", "AlignmentRequest", "Artifact", ("model:propose",), True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("modeling.proposal", "ProposalRequest", "Artifact", ("model:propose",), True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("review.action", "ReviewActionRequest", "ReviewAction", ("review:decide",), True, "INLINE", "WRITE", "REQUIRED"),
        OperationDefinition("review.replay", "ReviewRequest", "ReviewLog", _READ),
        OperationDefinition("review.finalize", "ReviewRequest", "ReviewLog", ("review:decide",), True, "INLINE", "WRITE", "REQUIRED"),
        OperationDefinition("compile.plan", "CompileRequest", "CompilationPlan", ("compile:run",), True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("compile.build", "CompileRequest", "CompilationResult", ("compile:run",), True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("compile.validate", "CompileRequest", "ValidationReport", ("compile:run",), True, "JOB", "READ", "REQUIRED"),
        OperationDefinition("compile.reproduce", "CompileRequest", "CompilationResult", ("compile:run",), True, "JOB", "READ", "REQUIRED"),
        OperationDefinition("package.inspect", "PackageRequest", "Package", ("package:read",), True),
        OperationDefinition("package.verify", "PackageRequest", "PackageVerification", ("package:read",), True),
        OperationDefinition("package.export", "PackageExportRequest", "ExportReceipt", ("package:export",), True, "JOB", "READ", "REQUIRED"),
        OperationDefinition("registry.import", "RegistryImportRequest", "PackageRecord", ("registry:import",), True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("registry.verify", "ProjectHandle", "RegistryVerification", _READ),
        OperationDefinition("change.diff", "DiffRequest", "DiffReport", ("project:read",), True, "JOB", "READ", "REQUIRED"),
        OperationDefinition("change.impact", "ImpactRequest", "ImpactReport", ("project:read",), True, "JOB", "READ", "REQUIRED"),
        OperationDefinition("change.regression", "RegressionRequest", "RegressionReport", ("project:read",), True, "JOB", "READ", "REQUIRED"),
        OperationDefinition("change.evaluate", "ChangeEvaluationRequest", "ChangeEvaluation", ("model:propose",), True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("release.review", "ReleaseReviewRequest", "ReviewLog", ("release:review",), True, "INLINE", "WRITE", "REQUIRED"),
        OperationDefinition("release.publish", "ReleasePublishRequest", "Release", ("release:publish",), True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("release.inspect", "ReleaseRequest", "Release", ("package:read",), True),
        OperationDefinition("environment.activate", "ActivationRequest", "ActivationReceipt", ("environment:activate",), True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("environment.rollback", "RollbackRequest", "ActivationReceipt", ("environment:rollback",), True, "JOB", "WRITE", "REQUIRED"),
        OperationDefinition("environment.inspect", "EnvironmentRequest", "EnvironmentPointer", _READ),
        OperationDefinition("oms.metadata", "MetadataRequest", "MetadataResult", ("package:read",), True),
        OperationDefinition("ods.query", "ObjectQueryRequest", "ObjectQueryResult", ("package:read",), True),
        OperationDefinition("visualization.export", "VisualizationExportRequest", "ExportReceipt", ("package:export",), True, "JOB", "READ", "REQUIRED"),
        OperationDefinition("integration.plan", "IntegrationPlanRequest", "IntegrationPlan", ("integration:configure",), True, "INLINE", "WRITE", "REQUIRED"),
        OperationDefinition("integration.review", "IntegrationApprovalRequest", "IntegrationApproval", ("integration:review",), True, "INLINE", "WRITE", "REQUIRED"),
        OperationDefinition("integration.execute", "IntegrationExecutionRequest", "IntegrationReceipt", ("integration:execute",), True, "JOB", "EXTERNAL", "REQUIRED"),
        OperationDefinition("integration.verify", "IntegrationVerificationRequest", "IntegrationReceipt", ("integration:execute",), True, "JOB", "READ", "REQUIRED"),
        OperationDefinition("workflow.enqueue", "WorkflowInvocation", "WorkflowReceipt", ("integration:execute",), True, "INLINE", "EXTERNAL", "REQUIRED"),
        OperationDefinition("job.get", "JobRequest", "JobRecord", _READ, False),
        OperationDefinition("job.events", "JobRequest", "JobEvents", _READ, False),
        OperationDefinition("operation.catalog", "CatalogRequest", "OperationCatalog", _READ, False),
    ]
    definitions.append(OperationDefinition("modeling.prepare", "ModelingPrepareRequest", "ModelingPreparation",
        ("model:propose",), True, "JOB", "WRITE", "REQUIRED"))
    definitions.append(OperationDefinition("release.candidate", "ReleaseCandidateRequest", "ReleaseCandidate",
        ("release:publish",), True, "JOB", "WRITE", "REQUIRED"))
    from .modeling import OPERATIONS as MODELING_OPERATIONS
    from .requests import REQUEST_MODELS
    definitions = [replace(definition, request_contract=REQUEST_MODELS[definition.operation_id].__name__)
                   if definition.operation_id in REQUEST_MODELS else definition for definition in definitions]
    return {definition.operation_id: replace(definition, execution_mode="JOB", side_effect_class="WRITE")
            if (definition.operation_id in MODELING_OPERATIONS and definition.operation_id != "review.replay") or definition.operation_id == "release.review"
            else definition for definition in definitions}


def coverage_matrix() -> list[dict[str, str]]:
    return [{"operation_id": operation_id, "service_handler": HANDLERS.get(operation_id),
             "status": "IMPLEMENTED_NOT_VERIFIED" if operation_id in HANDLERS else "DECLARED_ONLY",
             "blocked_reason": None if operation_id in HANDLERS else "No service-to-core handler",
             "api": "POST /api/v1/operations/{operation_id}"} for operation_id in sorted(build_operation_catalog())]


# Deliberately explicit executable coverage, not a reflection-based dispatcher.
# A catalogue declaration is not proof of a handler or a passing workflow.
HANDLERS = {
    "project.create": "kg_mnp.services.projects.create_project",
    "project.open": "kg_mnp.services.projects.inspect_project",
    "project.list": "kg_mnp.services.projects.list_projects",
    "project.validate": "kg_mnp.services.projects.inspect_project",
    "project.lock": "kg_mnp.services.projects.lock_project",
    "domain-pack.discover": "kg_mnp.services.packs.discover",
    "domain-pack.inspect": "kg_mnp.services.packs.discover",
    "registry.verify": "kg_mnp.lifecycle.registry.replay.verify_registry",
    "package.inspect": "kg_mnp.lifecycle.store.list_records",
    "release.inspect": "kg_mnp.lifecycle.store.list_records",
    "environment.inspect": "kg_mnp.lifecycle.store.list_records",
    "job.get": "kg_mnp.jobs.store.JobStore.get",
    "job.events": "kg_mnp.jobs.store.JobStore.events",
    "operation.catalog": "kg_mnp.services.facade.ApplicationService.operation_catalog",
}

from .sources import OPERATIONS as SOURCE_OPERATIONS

HANDLERS.update({name: "kg_mnp.services.sources.execute" for name in SOURCE_OPERATIONS})

from .modeling import OPERATIONS as MODELING_OPERATIONS

HANDLERS.update({name: "kg_mnp.services.modeling.execute" for name in MODELING_OPERATIONS})

from .compilation import OPERATIONS as COMPILATION_OPERATIONS

HANDLERS.update({name: "kg_mnp.services.compilation.execute" for name in COMPILATION_OPERATIONS})

from .lifecycle import OPERATIONS as LIFECYCLE_OPERATIONS

HANDLERS.update({name: "kg_mnp.services.lifecycle.execute" for name in LIFECYCLE_OPERATIONS})
