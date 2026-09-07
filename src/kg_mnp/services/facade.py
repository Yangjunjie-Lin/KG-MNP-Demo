from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from kg_mnp.lifecycle.registry.replay import verify_registry
from kg_mnp.lifecycle.store import list_records

from ..jobs.store import JobStore
from .audit import AuditLog
from .authorization import TokenStore
from .authorization_policy import authorize
from .errors import ServiceBoundaryError
from .idempotency import IdempotencyStore
from .models import (
    OperationDefinition,
    OperationRequest,
    OperationResult,
    PrincipalReference,
    ProjectHandle,
    ServiceConfiguration,
    path_for,
)
from .operations import HANDLERS, build_operation_catalog, coverage_matrix
from .packs import discover
from .projects import (
    can_access,
    create_project,
    get_project,
    inspect_project,
    list_projects,
    lock_project,
    require_access,
)


class ApplicationService:
    """Single authorization boundary for local, HTTP and worker callers."""

    def __init__(self, configuration: ServiceConfiguration):
        configuration.validate()
        self.configuration = configuration
        self.root = Path(configuration.workspace_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog = build_operation_catalog()
        self.tokens = TokenStore(path_for(configuration, "token_store_path", "service-data/tokens.json"))
        from .sessions import SessionStore
        self.sessions = SessionStore(self.root / "service-data" / "sessions.sqlite3", self.tokens)
        self.jobs = JobStore(path_for(configuration, "jobs_db_path", "service-data/jobs.sqlite3"))
        self.idempotency = IdempotencyStore(self.root / "service-data" / "requests.sqlite3")
        self.audit = AuditLog(self.root / "service-data" / "audit.jsonl")

    def runtime_check(self) -> dict[str, Any]:
        """Local CLI/authorized doctor only. Never use for public health."""
        return {"status": "SERVICE_READY", "host": self.configuration.host, "port": self.configuration.port,
                "operation_count": len(self.catalog), "workspace_root": str(self.root),
                "workbench_backend_gate": "NOT_READY"}

    def operation_catalog(self) -> list[dict[str, Any]]:
        return [{**asdict(item), "required_permissions": list(item.required_permissions),
                 "blocked_reason": None if item.operation_id in HANDLERS else "No service-to-core handler"}
                for item in self.catalog.values()]

    def capabilities(self, principal: PrincipalReference) -> dict:
        return {"capabilities": [{"operation_id": item.operation_id,
                                  "status": "BLOCKED_BY_POLICY" if not all(principal.can(p) for p in item.required_permissions)
                                  else "AVAILABLE" if item.operation_id in HANDLERS else "NOT_IMPLEMENTED"}
                                 for item in self.catalog.values()], "workbench_backend_gate": "NOT_READY"}

    def authenticate(self, authorization: str) -> PrincipalReference:
        scheme, _, token = authorization.partition(" ")
        if scheme == "Session":
            return self.sessions.resolve(token)[0]
        if scheme.lower() != "bearer":
            raise ServiceBoundaryError("AUTH_REQUIRED", "Bearer credential required", status_code=401)
        return self.tokens.authenticate(token)

    def _current(self, principal: PrincipalReference | None) -> PrincipalReference:
        if principal is None:
            raise ServiceBoundaryError("AUTH_REQUIRED", "authenticated principal is required", status_code=401)
        if principal.token_id:
            current = self.tokens.resolve(principal.token_id)
            if current.principal_id != principal.principal_id:
                raise ServiceBoundaryError("AUTH_INVALID", "credential identity changed", status_code=401)
            return current
        # Explicitly trusted in-process LocalClient only; never reconstructed
        # from a network body or a queued serialized Principal.
        return principal

    def _authorize_object(self, request, principal, operation):
        if operation.project_scope_required:
            require_access(principal, self._project(request))
        if request.operation_id == "project.open":
            project_id = request.parameters.get("project_id", request.project_id or "")
            require_access(principal, get_project(self.root, project_id))
        if request.operation_id in {"job.get", "job.events"}:
            self._job(str(request.parameters.get("job_id", "")), principal)

    def execute(self, request: OperationRequest, principal: PrincipalReference | None) -> OperationResult:
        principal = self._current(principal)
        operation = self.catalog.get(request.operation_id)
        if operation is None:
            raise ServiceBoundaryError("OPERATION_NOT_FOUND", "unknown operation", status_code=404)
        authorize(principal, operation, request)
        self._authorize_object(request, principal, operation)
        if request.operation_id not in HANDLERS:
            raise ServiceBoundaryError("OPERATION_BLOCKED", "service-to-core handler is not implemented", status_code=501)
        from .requests import validate_parameters
        validate_parameters(request)
        if operation.idempotency_policy == "REQUIRED" and not request.idempotency_key:
            raise ServiceBoundaryError("IDEMPOTENCY_REQUIRED", "Idempotency-Key is required", status_code=428)
        if operation.execution_mode == "JOB":
            if not principal.token_id:
                raise ServiceBoundaryError("JOB_CREDENTIAL_REQUIRED", "durable jobs require a revocable server credential", status_code=401)
            params = {**request.parameters, "__principal": {"principal_id": principal.principal_id, "token_id": principal.token_id}}
            try:
                job, _ = self.jobs.create(operation_id=request.operation_id, project_id=request.project_id, parameters=params,
                                          idempotency_key=request.idempotency_key, principal_id=principal.principal_id)
            except ValueError as exc:
                raise ServiceBoundaryError("IDEMPOTENCY_CONFLICT", str(exc), status_code=409) from exc
            return OperationResult(request.operation_id, "ACCEPTED", {"job_id": job.job_id, "status": job.status}, request.request_id, job.job_id)
        try:
            action = lambda: self._execute_inline(request, principal, operation)
            payload = self.idempotency.execute(request, principal, action) if operation.side_effect_class != "READ" else action()
            audit_id = self.audit.append(principal_id=principal.principal_id, operation_id=request.operation_id,
                                         project_id=request.project_id, request_id=request.request_id, outcome="SUCCEEDED", details={})
            return OperationResult(request.operation_id, "SUCCEEDED", payload, request.request_id, None, audit_id)
        except ServiceBoundaryError as exc:
            self.audit.append(principal_id=principal.principal_id, operation_id=request.operation_id, project_id=request.project_id,
                              request_id=request.request_id, outcome="BLOCKED", details={"code": exc.code})
            raise

    def execute_job(self, job, parameters: dict[str, Any]) -> dict[str, Any]:
        raw = dict(parameters)
        identity = raw.pop("__principal", {})
        if not identity.get("token_id"):
            raise ServiceBoundaryError("JOB_CREDENTIAL_REQUIRED", "job has no revocable credential", status_code=401)
        principal = self.tokens.resolve(identity["token_id"])
        if principal.principal_id != identity.get("principal_id"):
            raise ServiceBoundaryError("AUTH_INVALID", "job identity does not match credential", status_code=401)
        request = OperationRequest(job.operation_id, job.project_id, raw, idempotency_key=job.job_id)
        operation = self.catalog.get(job.operation_id)
        if not operation:
            raise ServiceBoundaryError("OPERATION_NOT_FOUND", "unknown queued operation", status_code=404)
        authorize(principal, operation, request)
        self._authorize_object(request, principal, operation)
        self.jobs.require_lease(job)
        from .compilation import OPERATIONS as COMPILATION_OPERATIONS
        from .compilation import execute as execute_compilation
        from .execution import execute_fenced
        from .integrations import OPERATIONS as INTEGRATION_OPERATIONS
        from .integrations import execute as execute_integration
        from .lifecycle import OPERATIONS as LIFECYCLE_OPERATIONS
        from .lifecycle import execute as execute_lifecycle
        from .modeling import OPERATIONS as MODELING_OPERATIONS
        from .modeling import execute as execute_modeling
        from .requests import validate_parameters
        from .sources import OPERATIONS, execute
        validate_parameters(request)
        if job.operation_id not in OPERATIONS | MODELING_OPERATIONS | COMPILATION_OPERATIONS | LIFECYCLE_OPERATIONS | INTEGRATION_OPERATIONS:
            raise ServiceBoundaryError("OPERATION_BLOCKED", "queued operation has no commit-fenced handler", status_code=501)
        if job.operation_id in OPERATIONS:
            handler = execute
        elif job.operation_id in MODELING_OPERATIONS:
            handler = execute_modeling
        elif job.operation_id in COMPILATION_OPERATIONS:
            handler = execute_compilation
        elif job.operation_id in LIFECYCLE_OPERATIONS:
            handler = execute_lifecycle
        else:
            handler = execute_integration
        return execute_fenced(self, job, request, principal, lambda project: handler(self, project, request, principal))

    def recover_job(self, job):
        from .execution import committed_result
        result = committed_result(self, job)
        return self.jobs.recover_committed(job.job_id, result) if result is not None else None

    def request_job_recovery(self, job_id, principal, *, mode, expected_attempt):
        principal = self._current(principal)
        from pydantic import ValidationError

        from .requests import JobRecoveryRequest
        try:
            JobRecoveryRequest(mode=mode, expected_attempt=expected_attempt)
        except ValidationError as exc:
            raise ServiceBoundaryError("REQUEST_INVALID", "recovery request does not match the resource contract", status_code=422) from exc
        if not principal.can("job:recover"):
            raise ServiceBoundaryError("FORBIDDEN", "missing permission: job:recover", status_code=403)
        job = self._job(job_id, principal)
        recovered = self.recover_job(job)
        if recovered is not None:
            return self._public_job(recovered, principal)
        if mode != "RETRY_LOCAL":
            raise ServiceBoundaryError("COMMIT_NOT_FOUND", "no verified core commit receipt exists", status_code=409)
        from .compilation import OPERATIONS as compilation
        from .lifecycle import OPERATIONS as lifecycle
        from .modeling import OPERATIONS as modeling
        from .sources import OPERATIONS as sources
        # External integration/workflow operations are deliberately excluded;
        # this is not a claim of safe replay for unknown external side effects.
        if job.operation_id not in sources | modeling | compilation | lifecycle:
            raise ServiceBoundaryError("RECOVERY_REQUIRED", "external or unknown operation requires explicit reconciliation", status_code=409)
        parameters = self.jobs.parameters(job_id)
        identity = parameters.get("__principal", {})
        original = self.tokens.resolve(identity.get("token_id", ""))
        if original.principal_id != identity.get("principal_id"):
            raise ServiceBoundaryError("AUTH_INVALID", "original job identity changed", status_code=401)
        request = OperationRequest(job.operation_id, job.project_id, {k:v for k,v in parameters.items() if k != "__principal"})
        authorize(original, self.catalog[job.operation_id], request)
        self._authorize_object(request, original, self.catalog[job.operation_id])
        try:
            from .coordination import metadata_lock
            with metadata_lock(self.tokens.path.with_suffix(".lock.sqlite3")):
                operator = self._current(principal)
                original = self.tokens.resolve(identity["token_id"])
                if not operator.can("job:recover"):
                    raise ServiceBoundaryError("FORBIDDEN", "job recovery grant changed", status_code=403)
                authorize(original, self.catalog[job.operation_id], request)
                queued = self.jobs.requeue_local(job_id, expected_attempt=expected_attempt,requested_by=operator.principal_id)
        except ValueError as exc:
            raise ServiceBoundaryError("JOB_RECOVERY_CONFLICT", "attempt is active, changed or cancelled", status_code=409) from exc
        return self._public_job(queued, principal)

    def _project(self, request: OperationRequest) -> ProjectHandle:
        if not request.project_id:
            raise ServiceBoundaryError("PROJECT_REQUIRED", "project scope is required", status_code=422)
        return get_project(self.root, request.project_id)

    def _job(self, job_id, principal, *, authorized_project=None):
        try:
            job = self.jobs.get(job_id)
        except KeyError as exc:
            raise ServiceBoundaryError("JOB_NOT_FOUND", "job was not found", status_code=404) from exc
        if job.project_id:
            project = authorized_project if authorized_project is not None and authorized_project.project_id == job.project_id else get_project(self.root, job.project_id)
            require_access(principal, project)
        owner = self.jobs.parameters(job_id).get("__principal", {}).get("principal_id")
        if owner != principal.principal_id and not principal.can("project:admin"):
            raise ServiceBoundaryError("JOB_FORBIDDEN", "job is outside principal scope", status_code=403)
        return job

    def cancel_job(self, job_id, principal):
        principal = self._current(principal)
        if not principal.can("job:cancel"):
            raise ServiceBoundaryError("FORBIDDEN", "missing permission: job:cancel", status_code=403)
        self._job(job_id, principal)
        return self._public_job(self.jobs.cancel(job_id), principal)

    def _public_job(self, job, principal):
        # Old persisted result/error/event payloads may contain filesystem paths.
        # Do not expose arbitrary legacy dictionaries across this boundary.
        from .execution import committed_result
        result = committed_result(self, job)
        if result is not None and job.status != "SUCCEEDED":
            job = self.jobs.recover_committed(job.job_id, result)
        return {"job_id": job.job_id, "operation_id": job.operation_id, "project_id": job.project_id,
                "status": job.status, "attempt": job.attempt, "result": result if principal.can("source:read") else None,
                "error": {"code": job.error.get("code", "JOB_FAILED"), "message": "job failed; consult authorized diagnostics"} if job.error else None}

    def _execute_inline(self, request: OperationRequest, principal: PrincipalReference, operation: OperationDefinition) -> dict[str, Any]:
        name, params, packs_root = request.operation_id, request.parameters, self.configuration.domain_packs_root
        if name == "project.create":
            return create_project(self.root, params["name"], principal, domain_pack=params["domain_pack"],
                                  domain_pack_version=params["domain_pack_version"], packs_root=packs_root).public_dict()
        if name == "project.list":
            return {"projects": [inspect_project(item, packs_root).public_dict() for item in list_projects(self.root) if can_access(principal, item)]}
        if name == "project.open":
            return inspect_project(get_project(self.root, params.get("project_id", request.project_id or "")), packs_root).public_dict()
        if name == "job.get":
            return self._public_job(self._job(params["job_id"], principal), principal)
        if name == "job.events":
            return {"events": [{"sequence": row["sequence"], "event_type": row["event_type"], "observed_at": row["observed_at"]}
                               for row in self.jobs.events(params["job_id"])]}
        if name == "operation.catalog":
            return {"operations": self.operation_catalog(), "coverage": coverage_matrix()}
        if name.startswith("domain-pack."):
            result = discover(packs_root)
            if name == "domain-pack.inspect":
                row = next((row for row in result["domain_packs"] if row["pack_id"] == params["pack_id"] and row["pack_version"] == params["pack_version"]), None)
                if row is None:
                    raise ServiceBoundaryError("DOMAIN_PACK_VERSION_UNAVAILABLE", "exact Domain Pack version is unavailable", status_code=404)
                return row
            return result
        project = self._project(request)
        if name == "project.validate":
            return inspect_project(project, packs_root).public_dict()
        if name == "project.lock":
            return lock_project(project, packs_root).public_dict()
        if inspect_project(project, packs_root).status != "VALID":
            raise ServiceBoundaryError("WORKSPACE_INVALID", "workspace is not valid; recovery or a new workspace is required", status_code=409)
        from .sources import OPERATIONS, execute
        if name in OPERATIONS:
            return execute(self, project, request, principal)
        if name == "review.replay":
            from .modeling import execute as execute_modeling
            return execute_modeling(self, project, request, principal)
        if name == "package.verify":
            from .compilation import execute as execute_compilation
            return execute_compilation(self, project, request, principal)
        if name in {"oms.metadata", "ods.query","object.trace"}:
            from .lifecycle import execute as execute_lifecycle
            return execute_lifecycle(self, project, request, principal)
        if name == "registry.verify":
            return verify_registry(project.registry_root)
        if name in {"package.inspect", "release.inspect"}:
            kind = "package" if name == "package.inspect" else "release"
            rows = list_records(project.registry_root, "records/" + kind + "s")
            row = next((row for row in rows if row.get(kind + "_id") == params[kind + "_id"]), None)
            if row is None:
                raise ServiceBoundaryError("ARTIFACT_NOT_FOUND", "artifact was not found in project", status_code=404)
            return row
        if name == "environment.inspect":
            rows = list_records(project.registry_root, "state")
            row = next((row for row in rows if row.get("environment_id") == params["environment_id"] and row.get("manifest_kind") == "KG_MNP_ENVIRONMENT_POINTER"), None)
            if row is None:
                raise ServiceBoundaryError("ARTIFACT_NOT_FOUND", "environment pointer was not found", status_code=404)
            return row
        raise ServiceBoundaryError("OPERATION_BLOCKED", "operation handler is not implemented", status_code=501)
