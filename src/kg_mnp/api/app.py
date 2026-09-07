from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest


def create_app(service: ApplicationService) -> FastAPI:
    app = FastAPI(title="KG-MNP Toolchain API", version="0.7.0", openapi_version="3.1.0")
    app.state.service = service
    if service.configuration.allowed_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(service.configuration.allowed_origins), allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"], allow_credentials=False)

    @app.exception_handler(ServiceBoundaryError)
    async def service_error(_request: Request, exc: ServiceBoundaryError):
        return JSONResponse(exc.to_dict(), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        return JSONResponse({"error": {"code": "INTERNAL_ERROR", "message": "internal service error", "retryable": False, "details": []}}, status_code=500)

    @app.get("/healthz", operation_id="healthz")
    def healthz():
        return service.runtime_check()

    @app.get("/api/v1/health", operation_id="serviceHealth")
    def health(authorization: str | None = Header(default=None)):
        if not authorization:
            raise ServiceBoundaryError("AUTH_REQUIRED", "Bearer credential required", status_code=401)
        service.authenticate(authorization)
        return service.runtime_check()

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
    def create_project(payload: dict[str, Any] = Body(...), authorization: str | None = Header(default=None), request_id: str | None = Header(default=None, alias="X-Request-ID")):  # noqa: B008
        principal = service.authenticate(authorization or "")
        request = OperationRequest("project.create", None, {"name": payload.get("name")}, request_id=request_id or OperationRequest.__dataclass_fields__["request_id"].default_factory())
        return service.execute(request, principal).payload

    @app.get("/api/v1/jobs/{job_id}", operation_id="getJob")
    def get_job(job_id: str, authorization: str | None = Header(default=None)):
        principal = service.authenticate(authorization or "")
        return service.execute(OperationRequest("job.get", None, {"job_id": job_id}), principal).payload

    @app.get("/api/v1/jobs/{job_id}/events", operation_id="getJobEvents")
    def get_job_events(job_id: str, authorization: str | None = Header(default=None)):
        principal = service.authenticate(authorization or "")
        return service.execute(OperationRequest("job.events", None, {"job_id": job_id}), principal).payload

    return app
