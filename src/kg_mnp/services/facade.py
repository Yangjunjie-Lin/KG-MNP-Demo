from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.lifecycle.registry.replay import verify_registry
from kg_mnp.lifecycle.store import list_records

from ..jobs.store import JobStore
from .audit import AuditLog
from .authorization import TokenStore
from .authorization_policy import authorize
from .errors import ServiceBoundaryError
from .models import (
    OperationDefinition,
    OperationRequest,
    OperationResult,
    PrincipalReference,
    ProjectHandle,
    ServiceConfiguration,
    path_for,
)
from .operations import build_operation_catalog, coverage_matrix
from .projects import create_project, get_project, list_projects


class ApplicationService:
    """The only business entrypoint used by the new CLI, SDK and REST API."""

    def __init__(self, configuration: ServiceConfiguration):
        configuration.validate()
        self.configuration = configuration
        root = Path(configuration.workspace_root)
        root.mkdir(parents=True, exist_ok=True)
        self.catalog = build_operation_catalog()
        self.tokens = TokenStore(path_for(configuration, "token_store_path", "service-data/tokens.json"))
        self.jobs = JobStore(path_for(configuration, "jobs_db_path", "service-data/jobs.sqlite3"))
        self.audit = AuditLog(root / "service-data" / "audit.jsonl")

    def runtime_check(self) -> dict[str, Any]:
        return {"status": "SERVICE_READY", "host": self.configuration.host, "port": self.configuration.port, "operation_count": len(self.catalog), "workspace_root": str(Path(self.configuration.workspace_root).resolve())}

    def operation_catalog(self) -> list[dict[str, Any]]:
        return [{"operation_id": item.operation_id, "request_contract": item.request_contract, "response_contract": item.response_contract, "required_permissions": list(item.required_permissions), "project_scope_required": item.project_scope_required, "execution_mode": item.execution_mode, "side_effect_class": item.side_effect_class, "idempotency_policy": item.idempotency_policy, "precondition_policy": item.precondition_policy, "audit_policy": item.audit_policy, "blocked_reason": item.blocked_reason} for item in self.catalog.values()]

    def authenticate(self, authorization: str) -> PrincipalReference:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer":
            raise ServiceBoundaryError("AUTH_REQUIRED", "Bearer credential required", status_code=401)
        return self.tokens.authenticate(token)

    def execute(self, request: OperationRequest, principal: PrincipalReference | None) -> OperationResult:
        if principal is None:
            raise ServiceBoundaryError("AUTH_REQUIRED", "authenticated principal is required", status_code=401)
        operation = self.catalog.get(request.operation_id)
        if operation is None:
            raise ServiceBoundaryError("OPERATION_NOT_FOUND", "unknown operation", status_code=404)
        authorize(principal, operation, request)
        if operation.execution_mode == "JOB":
            if operation.idempotency_policy == "REQUIRED" and not request.idempotency_key:
                raise ServiceBoundaryError("IDEMPOTENCY_REQUIRED", "Idempotency-Key is required", status_code=428)
            params = {**request.parameters, "__principal": principal.to_dict()}
            try:
                job, existing = self.jobs.create(operation_id=request.operation_id, project_id=request.project_id, parameters=params, idempotency_key=request.idempotency_key)
            except ValueError as exc:
                raise ServiceBoundaryError("IDEMPOTENCY_CONFLICT", str(exc), status_code=409) from exc
            audit_id = self.audit.append(principal_id=principal.principal_id, operation_id=request.operation_id, project_id=request.project_id, request_id=request.request_id, outcome="ACCEPTED" if not existing else "IDEMPOTENT_REPLAY", details={"job_id": job.job_id})
            return OperationResult(request.operation_id, "ACCEPTED", {"job_id": job.job_id, "status": job.status}, request.request_id, job.job_id, audit_id)
        try:
            payload = self._execute_inline(request, principal, operation)
            audit_id = self.audit.append(principal_id=principal.principal_id, operation_id=request.operation_id, project_id=request.project_id, request_id=request.request_id, outcome="SUCCEEDED", details={"semantic": payload.get("semantic_digest") if isinstance(payload, dict) else None})
            return OperationResult(request.operation_id, "SUCCEEDED", payload, request.request_id, None, audit_id)
        except ServiceBoundaryError as exc:
            self.audit.append(principal_id=principal.principal_id, operation_id=request.operation_id, project_id=request.project_id, request_id=request.request_id, outcome="BLOCKED", details={"code": exc.code})
            raise

    def execute_job(self, job, parameters: dict[str, Any]) -> dict[str, Any]:
        raw = dict(parameters)
        principal_data = raw.pop("__principal", None)
        if not principal_data:
            raise ServiceBoundaryError("JOB_PRINCIPAL_MISSING", "job has no authenticated principal")
        principal = PrincipalReference(principal_data["principal_id"], principal_data["principal_type"], frozenset(principal_data["permissions"]), frozenset(principal_data["project_ids"]), principal_data.get("token_id"))
        request = OperationRequest(job.operation_id, job.project_id, raw)
        operation = self.catalog[job.operation_id]
        authorize(principal, operation, request)
        return self._execute_inline(request, principal, operation)

    def _project(self, request: OperationRequest) -> ProjectHandle:
        if not request.project_id:
            raise ServiceBoundaryError("PROJECT_REQUIRED", "project scope is required", status_code=422)
        return get_project(Path(self.configuration.workspace_root), request.project_id)

    def _execute_inline(self, request: OperationRequest, principal: PrincipalReference, operation: OperationDefinition) -> dict[str, Any]:
        if request.operation_id == "project.create":
            handle = create_project(Path(self.configuration.workspace_root), str(request.parameters.get("name", "")), principal)
            return asdict(handle)
        if request.operation_id == "project.list":
            return {"projects": [asdict(item) for item in list_projects(Path(self.configuration.workspace_root))]}
        if request.operation_id == "project.open":
            return asdict(get_project(Path(self.configuration.workspace_root), str(request.parameters.get("project_id", request.project_id or ""))))
        if request.operation_id == "job.get":
            return asdict(self.jobs.get(str(request.parameters.get("job_id"))))
        if request.operation_id == "job.events":
            return {"events": self.jobs.events(str(request.parameters.get("job_id")))}
        if request.operation_id == "operation.catalog":
            return {"operations": self.operation_catalog(), "coverage": coverage_matrix()}
        project = self._project(request)
        if request.operation_id == "project.validate":
            result = verify_registry(project.root)
            return {"project_id": project.project_id, **result}
        if request.operation_id == "registry.verify":
            return verify_registry(project.root)
        if request.operation_id == "package.inspect":
            package_id = request.parameters.get("package_id")
            rows = list_records(project.root, "records/packages")
            return next((row for row in rows if row.get("package_id") == package_id), {"status": "NOT_FOUND"})
        if request.operation_id == "release.inspect":
            release_id = request.parameters.get("release_id")
            rows = list_records(project.root, "records/releases")
            return next((row for row in rows if row.get("release_id") == release_id), {"status": "NOT_FOUND"})
        if request.operation_id == "environment.inspect":
            environment_id = request.parameters.get("environment_id")
            pointer = project.root / "state" / f"environment-pointer-{str(environment_id).rsplit(':', 1)[-1]}.json"
            if not pointer.is_file():
                raise ServiceBoundaryError("ARTIFACT_NOT_FOUND", "environment pointer was not found", status_code=404)
            return json.loads(pointer.read_bytes())
        if request.operation_id == "project.lock":
            lock = project.root / "project.lock.json"
            lock.write_text(json.dumps({"project_id": project.project_id, "status": "LOCKED", "lock_digest": stable_urn("project-lock", {"project_id": project.project_id})}, sort_keys=True), encoding="utf-8")
            return {**asdict(project), "status": "LOCKED"}
        if request.operation_id == "domain-pack.discover":
            return {"domain_packs": []}
        raise ServiceBoundaryError("OPERATION_BLOCKED", f"operation handler is not enabled in this service release: {request.operation_id}", status_code=501)
