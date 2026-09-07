from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest
from kg_mnp.services.requests import ProjectCreateRequest


def create_app(service: ApplicationService) -> FastAPI:
    app = FastAPI(title="KG-MNP Toolchain API", version="0.7.0", openapi_version="3.1.0")
    app.state.service = service

    @app.middleware("http")
    async def boundary_headers(request: Request, call_next):
        origin = request.headers.get("origin")
        same_origin = str(request.base_url).rstrip("/")
        if origin and origin != same_origin and origin not in service.configuration.allowed_origins:
            response = JSONResponse({"error": {"code": "ORIGIN_FORBIDDEN", "message": "origin is not allowed"}}, status_code=403)
        else:
            response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response
    if service.configuration.allowed_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(service.configuration.allowed_origins), allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"], allow_credentials=False)

    @app.exception_handler(ServiceBoundaryError)
    async def service_error(_request: Request, exc: ServiceBoundaryError):
        return JSONResponse(exc.to_dict(), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        return JSONResponse({"error": {"code": "INTERNAL_ERROR", "message": "internal service error", "retryable": False, "details": []}}, status_code=500)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _exc: RequestValidationError):
        return JSONResponse({"error": {"code": "REQUEST_INVALID", "message": "request does not match the resource contract", "retryable": False, "details": []}}, status_code=422)

    @app.get("/healthz", operation_id="healthz")
    def healthz():
        return {"status": "ALIVE"}

    @app.get("/api/v1/health", operation_id="serviceHealth")
    def health(authorization: str | None = Header(default=None)):
        if not authorization:
            raise ServiceBoundaryError("AUTH_REQUIRED", "Bearer credential required", status_code=401)
        service.authenticate(authorization)
        return {"status": "ALIVE"}

    @app.get("/health/live", operation_id="liveness")
    def liveness():
        return {"status": "ALIVE"}

    @app.get("/api/v1/me", operation_id="getPrincipal")
    def me(authorization: str | None = Header(default=None)):
        principal = service.authenticate(authorization or "")
        return {key: value for key, value in principal.to_dict().items() if key != "token_id"}

    @app.get("/api/v1/capabilities", operation_id="getCapabilities")
    def capabilities(authorization: str | None = Header(default=None)):
        return service.capabilities(service.authenticate(authorization or ""))

    @app.get("/api/v1/doctor", operation_id="getDoctor")
    def doctor(authorization: str | None = Header(default=None)):
        principal = service.authenticate(authorization or "")
        if not principal.can("service:admin"):
            raise ServiceBoundaryError("FORBIDDEN", "missing permission: service:admin", status_code=403)
        return service.runtime_check()

    @app.get("/api/v1/domain-packs", operation_id="listDomainPacks")
    def domain_packs(authorization: str | None = Header(default=None)):
        return service.execute(OperationRequest("domain-pack.discover"), service.authenticate(authorization or "")).payload

    @app.get("/api/v1/operations", operation_id="listOperations")
    def operations(authorization: str | None = Header(default=None)):
        principal = service.authenticate(authorization or "")
        if not principal.can("project:read"):
            raise ServiceBoundaryError("FORBIDDEN", "missing permission: project:read", status_code=403)
        return {"operations": service.operation_catalog()}

    @app.post("/api/v1/operations/{operation_id}", operation_id="executeOperation")
    def execute_operation(operation_id: str, payload: dict[str, Any] = Body(default_factory=dict), authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID")):  # noqa: B008
        principal = service.authenticate(authorization or "")
        project_id = payload.pop("project_id", None)
        request = OperationRequest(operation_id, project_id, payload, idempotency_key, request_id or OperationRequest.__dataclass_fields__["request_id"].default_factory())
        result = service.execute(request, principal)
        status = 202 if result.status == "ACCEPTED" else 200
        return JSONResponse({"operation_id": result.operation_id, "status": result.status, "payload": result.payload, "request_id": result.request_id, "job_id": result.job_id, "audit_id": result.audit_id}, status_code=status)

    @app.get("/api/v1/projects", operation_id="listProjects")
    def projects(authorization: str | None = Header(default=None)):
        principal = service.authenticate(authorization or "")
        return service.execute(OperationRequest("project.list"), principal).payload

    @app.post("/api/v1/projects", operation_id="createProject")
    def create_project(payload: ProjectCreateRequest, authorization: str | None = Header(default=None), request_id: str | None = Header(default=None, alias="X-Request-ID"), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
        principal = service.authenticate(authorization or "")
        request = OperationRequest("project.create", None, payload.model_dump(), idempotency_key=idempotency_key, request_id=request_id or OperationRequest.__dataclass_fields__["request_id"].default_factory())
        return service.execute(request, principal).payload

    @app.get("/api/v1/projects/{project_id}", operation_id="openProject")
    def open_project(project_id: str, authorization: str | None = Header(default=None)):
        return service.execute(OperationRequest("project.open", project_id), service.authenticate(authorization or "")).payload

    @app.get("/api/v1/projects/{project_id}/validation", operation_id="validateProject")
    def validate_project(project_id: str, authorization: str | None = Header(default=None)):
        return service.execute(OperationRequest("project.validate", project_id), service.authenticate(authorization or "")).payload

    @app.post("/api/v1/projects/{project_id}/lock", operation_id="lockProject")
    def lock_project(project_id: str, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
        return service.execute(OperationRequest("project.lock", project_id, idempotency_key=idempotency_key), service.authenticate(authorization or "")).payload

    @app.get("/api/v1/jobs/{job_id}", operation_id="getJob")
    def get_job(job_id: str, authorization: str | None = Header(default=None)):
        principal = service.authenticate(authorization or "")
        return service.execute(OperationRequest("job.get", None, {"job_id": job_id}), principal).payload

    @app.get("/api/v1/jobs/{job_id}/events", operation_id="getJobEvents")
    def get_job_events(job_id: str, authorization: str | None = Header(default=None)):
        principal = service.authenticate(authorization or "")
        return service.execute(OperationRequest("job.events", None, {"job_id": job_id}), principal).payload

    @app.post("/api/v1/jobs/{job_id}/cancel", operation_id="cancelJob")
    def cancel_job(job_id: str, authorization: str | None = Header(default=None)):
        return service.cancel_job(job_id, service.authenticate(authorization or ""))

    return app
