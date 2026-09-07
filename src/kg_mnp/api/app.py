from __future__ import annotations

import re
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import Body, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from kg_mnp import __version__
from kg_mnp.services.errors import ServiceBoundaryError
from kg_mnp.services.facade import ApplicationService
from kg_mnp.services.models import OperationRequest
from kg_mnp.services.requests import (
    ChangeEvaluationRequest,
    CompileBuildRequest,
    CompilePlanRequest,
    ConsumerRequest,
    DiffReferenceRequest,
    DiffRequest,
    EnvironmentCreateRequest,
    EnvironmentExecutionRequest,
    EnvironmentProposalRequest,
    EnvironmentReviewRequest,
    FeedbackRequest,
    IngestionPlanRequest,
    IngestionRunRequest,
    IntegrationExecuteRequest,
    IntegrationPlanRequest,
    IntegrationReviewRequest,
    JobRecoveryRequest,
    ModelingPrepareRequest,
    ObjectRequest,
    ObjectTraceRequest,
    PackageRequest,
    ProjectCreateRequest,
    ProposalRequest,
    RegressionRequest,
    ReleaseCandidateRequest,
    ReleasePublishRequest,
    ReleaseReviewRequest,
    ReviewActionRequest,
    ReviewRequest,
    ScopeApprovalRequest,
    ScopeRequest,
    SourceBatchRequest,
    WorkflowRequest,
)


def create_app(service: ApplicationService) -> FastAPI:
    app = FastAPI(title="KG-MNP Toolchain API", version=__version__, openapi_version="3.1.0")
    app.state.service = service

    @app.middleware("http")
    async def boundary_headers(request: Request, call_next):
        path = request.scope.get("path", "")
        host = request.headers.get("host", "")
        # Check raw ASGI/Host values before URL reconstruction or filesystem
        # resolution. In particular, never let a Windows UNC URL reach static
        # path resolution (which can trigger SMB before containment is checked).
        if (not path.startswith("/") or "\\" in path or any(ord(c)<32 for c in path)
                or not re.fullmatch(r"(?:\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+)(?::[0-9]{1,5})?", host)):
            return JSONResponse({"error":{"code":"REQUEST_TARGET_INVALID","message":"invalid request target or Host"}}, status_code=400,
                headers={"Content-Security-Policy":"default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
                         "X-Content-Type-Options":"nosniff","X-Frame-Options":"DENY","Cache-Control":"no-store"})
        origin = request.headers.get("origin")
        same_origin = str(request.base_url).rstrip("/")
        if origin and origin != same_origin and origin not in service.configuration.allowed_origins:
            response = JSONResponse({"error": {"code": "ORIGIN_FORBIDDEN", "message": "origin is not allowed"}}, status_code=403)
        else:
            try:
                if request.method in {"POST", "PUT", "PATCH"} and not path.endswith("/sources"):
                    body = bytearray()
                    async for chunk in request.stream():
                        body.extend(chunk)
                        if len(body) > 1024 * 1024:
                            raise ServiceBoundaryError("REQUEST_TOO_LARGE", "JSON request byte limit exceeded", status_code=413)
                    request._body = bytes(body)
                cookie = request.cookies.get("kgmnp_session")
                if cookie and not request.headers.get("authorization"):
                    _principal, csrf = service.sessions.resolve(cookie)
                    if request.method not in {"GET", "HEAD", "OPTIONS"} and (
                        origin != same_origin or not secrets.compare_digest(request.headers.get("x-csrf-token", ""), csrf)
                    ):
                        raise ServiceBoundaryError("CSRF_FORBIDDEN", "same-origin CSRF proof required", status_code=403)
                    request.scope["headers"] = [*request.scope["headers"], (b"authorization", ("Session " + cookie).encode())]
                response = await call_next(request)
            except ServiceBoundaryError as exc:
                response = JSONResponse(exc.to_dict(), status_code=exc.status_code)
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        if not path.startswith(("/api/", "/health")):
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
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

    @app.post("/api/v1/session", operation_id="createBrowserSession")
    def login(request: Request, authorization: str | None = Header(default=None)):
        origin = request.headers.get("origin")
        same_origin = str(request.base_url).rstrip("/")
        insecure_allowed = service.configuration.allow_insecure_loopback_session and request.url.hostname in {"127.0.0.1", "localhost", "::1"}
        if origin != same_origin or (request.url.scheme != "https" and not insecure_allowed):
            raise ServiceBoundaryError("SESSION_ORIGIN_FORBIDDEN", "session requires same-origin HTTPS or explicit loopback development", status_code=403)
        principal = service.authenticate(authorization or "")
        if request.cookies.get("kgmnp_session"):
            service.sessions.revoke(request.cookies["kgmnp_session"])
        opaque, csrf = service.sessions.create(principal)
        response = JSONResponse({"principal": {k: v for k, v in principal.to_dict().items() if k != "token_id"}, "csrf_token": csrf})
        response.set_cookie("kgmnp_session", opaque, max_age=1800, secure=not insecure_allowed, httponly=True, samesite="strict", path="/")
        return response

    @app.get("/api/v1/session", operation_id="inspectBrowserSession")
    def session(request: Request):
        principal, csrf = service.sessions.resolve(request.cookies.get("kgmnp_session", ""))
        return {"principal": {k: v for k, v in principal.to_dict().items() if k != "token_id"}, "csrf_token": csrf}

    @app.post("/api/v1/session/logout", operation_id="logoutBrowserSession")
    def logout(request: Request):
        opaque = request.cookies.get("kgmnp_session", "")
        service.sessions.resolve(opaque)
        service.sessions.revoke(opaque)
        response = JSONResponse({"status": "SIGNED_OUT", "background_jobs": "RETAIN_CURRENT_TOKEN_GRANT"})
        response.delete_cookie("kgmnp_session", path="/", httponly=True, samesite="strict")
        return response

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

    @app.get("/api/v1/projects/{project_id}/state", operation_id="readProjectState")
    def project_state(project_id: str, authorization: str | None = Header(default=None)):
        principal = service.authenticate(authorization or "")
        from kg_mnp.services.authorization_policy import authorize
        from kg_mnp.services.projects import (
            load_catalog,
            project_from_catalog,
            require_access,
        )
        authorize(principal,service.catalog["project.open"],OperationRequest("project.open",project_id))
        catalog = load_catalog(service.root)
        project_handle=project_from_catalog(service.root,catalog,project_id)
        require_access(principal,project_handle)
        # Operational projection only: do not cache or advertise an artifact
        # validation verdict. Explicit readers/validators verify their artifacts.
        opened={**project_handle.public_dict(),"status":"OPEN","validation_status":"NOT_RUN_BY_STATE_PROJECTION"}
        if not principal.can("source:read") or not principal.can("package:read"):
            raise ServiceBoundaryError("FORBIDDEN", "source:read and package:read required for combined workspace view", status_code=403)
        from kg_mnp.lifecycle.registry.head import read_head
        results = [{"job_id": job_id, "operation": record["context"]["operation_id"],
                    "revision": record["authority_revision"], "result": record["result"]}
                   for job_id, record in catalog.get("commits", {}).items() if record["context"]["project_id"] == project_id]
        jobs = []
        for job in service.jobs.list_project(project_id):
            try:
                service._job(job.job_id, principal,authorized_project=project_handle)
            except ServiceBoundaryError:
                continue
            jobs.append({"job_id": job.job_id, "operation_id": job.operation_id, "status": job.status,
                         "attempt":job.attempt,
                         "error": {"code": job.error.get("code")} if job.error else None})
        return {"project": opened, "results": sorted(results, key=lambda row: row["revision"]), "jobs": jobs,
                "registry_head": read_head(project_handle.registry_root)["head_hash"]}

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

    @app.post("/api/v1/jobs/{job_id}/recovery", operation_id="recoverJob")
    def recover_job(job_id: str, payload: JobRecoveryRequest, authorization: str | None = Header(default=None)):
        return service.request_job_recovery(job_id, service.authenticate(authorization or ""),
            mode=payload.mode, expected_attempt=payload.expected_attempt)

    @app.post("/api/v1/projects/{project_id}/sources", operation_id="uploadSource", status_code=202)
    async def upload_source(project_id: str, request: Request, authorization: str | None = Header(default=None),
                            filename: str = Header(alias="X-Filename"), idempotency_key: str | None = Header(default=None)):
        from kg_mnp.services.uploads import receive_upload
        result = await receive_upload(service, project_id, service.authenticate(authorization or ""), request.stream(),
                                      filename=unquote(filename), media_type=request.headers.get("content-type", "application/octet-stream"),
                                      idempotency_key=idempotency_key)
        return result.payload

    def resource(operation, project_id, authorization, parameters=None, key=None):
        result = service.execute(OperationRequest(operation, project_id, parameters or {}, key), service.authenticate(authorization or ""))
        return JSONResponse(result.payload, status_code=202 if result.job_id else 200)

    @app.get("/api/v1/projects/{project_id}/sources", operation_id="listSources")
    def list_sources(project_id: str, authorization: str | None = Header(default=None)):
        return resource("source.list", project_id, authorization)

    @app.post("/api/v1/projects/{project_id}/source-batches",operation_id="createSourceBatch",status_code=202)
    def source_batch(project_id:str,payload:SourceBatchRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("source.batch",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.get("/api/v1/projects/{project_id}/sources/{source_id}", operation_id="inspectSource")
    def source(project_id: str, source_id: str, authorization: str | None = Header(default=None)):
        return resource("source.inspect", project_id, authorization, {"source_id": source_id})

    @app.get("/api/v1/projects/{project_id}/sources/{source_id}/content", operation_id="downloadSource")
    def source_content(project_id: str, source_id: str, authorization: str | None = Header(default=None)):
        principal = service.authenticate(authorization or "")
        req = OperationRequest("source.verify", project_id, {"source_id": source_id})
        service.execute(req, principal)
        from kg_mnp.ingestion.source_store import SourceStore
        store = SourceStore(service._project(req).root)
        content = store.blob_for(store.verify_source(source_id)).read_bytes()
        # Raw untrusted content is an attachment, never active browser HTML/PDF.
        return Response(content, media_type="application/octet-stream",
                        headers={"Content-Disposition": 'attachment; filename="source.bin"'})

    @app.post("/api/v1/projects/{project_id}/ingestion/plans", operation_id="planIngestion", status_code=202)
    def plan_ingestion(project_id: str, payload: IngestionPlanRequest, authorization: str | None = Header(default=None),
                       idempotency_key: str | None = Header(default=None)):
        return resource("ingestion.plan", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/ingestion/runs", operation_id="runIngestion", status_code=202)
    def run_ingestion(project_id: str, payload: IngestionRunRequest, authorization: str | None = Header(default=None),
                      idempotency_key: str | None = Header(default=None)):
        return resource("ingestion.run", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.get("/api/v1/projects/{project_id}/ingestion/runs/{run_id}", operation_id="inspectIngestion")
    def inspect_ingestion(project_id: str, run_id: str, authorization: str | None = Header(default=None)):
        return resource("ingestion.inspect", project_id, authorization, {"run_id": run_id})

    @app.get("/api/v1/projects/{project_id}/evidence", operation_id="listEvidence")
    def evidence(project_id: str, run_id: str, item_id: str | None = None, authorization: str | None = Header(default=None)):
        return resource("evidence.list", project_id, authorization, {"run_id": run_id, "item_id": item_id})

    @app.post("/api/v1/projects/{project_id}/modeling/scopes", operation_id="createScope", status_code=202)
    def scope(project_id: str, payload: ScopeRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("modeling.scope", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/modeling/scope-approvals", operation_id="approveScope", status_code=202)
    def approve(project_id: str, payload: ScopeApprovalRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("modeling.scope.approve", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/modeling/preparations", operation_id="prepareModeling", status_code=202)
    def prepare(project_id: str, payload: ModelingPrepareRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("modeling.prepare", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/modeling/proposals", operation_id="proposeModeling", status_code=202)
    def propose(project_id: str, payload: ProposalRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("modeling.proposal", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/reviews/actions", operation_id="applyReviewAction", status_code=202)
    def review_action(project_id: str, payload: ReviewActionRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("review.action", project_id, authorization, payload.model_dump(exclude_unset=True), idempotency_key)

    @app.get("/api/v1/projects/{project_id}/reviews/{review_id}", operation_id="replayReview")
    def replay_review(project_id: str, review_id: str, authorization: str | None = Header(default=None)):
        return resource("review.replay", project_id, authorization, {"review_id": review_id})

    @app.post("/api/v1/projects/{project_id}/reviews/finalizations", operation_id="finalizeReview", status_code=202)
    def finalize_review(project_id: str, payload: ReviewRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("review.finalize", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/compilations/plans", operation_id="planCompilation", status_code=202)
    def compilation_plan(project_id: str, payload: CompilePlanRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("compile.plan", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/compilations/builds", operation_id="buildCompilation", status_code=202)
    def compilation_build(project_id: str, payload: CompileBuildRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("compile.build", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/imports", operation_id="importRegistryPackage", status_code=202)
    def registry_import(project_id: str, payload: PackageRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("registry.import", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/release-candidates", operation_id="createReleaseCandidate", status_code=202)
    def release_candidate(project_id: str, payload: ReleaseCandidateRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("release.candidate", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/release-reviews", operation_id="reviewRelease", status_code=202)
    def release_review(project_id: str, payload: ReleaseReviewRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("release.review", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/releases", operation_id="publishRelease", status_code=202)
    def release_publish(project_id: str, payload: ReleasePublishRequest, authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        return resource("release.publish", project_id, authorization, payload.model_dump(), idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/diffs",operation_id="comparePackages",status_code=202)
    def compare_packages(project_id:str,payload:DiffRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("change.diff",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/impacts",operation_id="analyzeImpact",status_code=202)
    def impact(project_id:str,payload:DiffReferenceRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("change.impact",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/regressions",operation_id="executeRegression",status_code=202)
    def regression(project_id:str,payload:RegressionRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("change.regression",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/evaluations",operation_id="evaluateChange",status_code=202)
    def evaluate(project_id:str,payload:ChangeEvaluationRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("change.evaluate",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/environments",operation_id="createEnvironment",status_code=202)
    def environment_create(project_id:str,payload:EnvironmentCreateRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("environment.create",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/environment-proposals",operation_id="proposeEnvironment",status_code=202)
    def environment_propose(project_id:str,payload:EnvironmentProposalRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("environment.propose",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/environment-reviews",operation_id="reviewEnvironment",status_code=202)
    def environment_review(project_id:str,payload:EnvironmentReviewRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("environment.review",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/activations",operation_id="activateEnvironment",status_code=202)
    def environment_activate(project_id:str,payload:EnvironmentExecutionRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("environment.activate",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/rollbacks",operation_id="rollbackEnvironment",status_code=202)
    def environment_rollback(project_id:str,payload:EnvironmentExecutionRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("environment.rollback",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/integrations/plans",operation_id="planIntegration",status_code=202)
    def integration_plan(project_id:str,payload:IntegrationPlanRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("integration.plan",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/integrations/reviews",operation_id="reviewIntegration",status_code=202)
    def integration_review(project_id:str,payload:IntegrationReviewRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("integration.review",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/integrations/executions",operation_id="executeIntegration",status_code=202)
    def integration_execute(project_id:str,payload:IntegrationExecuteRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("integration.execute",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/integrations/observations",operation_id="observeIntegration",status_code=202)
    def integration_observe(project_id:str,payload:IntegrationExecuteRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("integration.verify",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/integrations/workflow-requests",operation_id="enqueueWorkflow",status_code=202)
    def enqueue_workflow(project_id:str,payload:WorkflowRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("workflow.enqueue",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/feedback",operation_id="submitFeedback",status_code=202)
    def feedback(project_id:str,payload:FeedbackRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("feedback.add",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.post("/api/v1/projects/{project_id}/lifecycle/consumers",operation_id="registerConsumer",status_code=202)
    def consumer(project_id:str,payload:ConsumerRequest,authorization:str|None=Header(default=None),idempotency_key:str|None=Header(default=None)):
        return resource("consumer.register",project_id,authorization,payload.model_dump(),idempotency_key)

    @app.get("/api/v1/projects/{project_id}/metadata", operation_id="inspectMetadata")
    def metadata(project_id: str, package_id: str, limit: int = 100, offset: int = 0, release_id: str | None = None, authorization: str | None = Header(default=None)):
        return resource("oms.metadata", project_id, authorization, {"package_id": package_id, "release_id":release_id, "limit": limit, "offset": offset})

    @app.get("/api/v1/projects/{project_id}/environment-pointer",operation_id="getEnvironmentPointer")
    def environment_pointer(project_id:str,environment_id:str,authorization:str|None=Header(default=None)):
        return resource("environment.inspect",project_id,authorization,{"environment_id":environment_id})

    @app.post("/api/v1/projects/{project_id}/objects/query", operation_id="queryObjects")
    def objects(project_id: str, payload: ObjectRequest, authorization: str | None = Header(default=None)):
        return resource("ods.query", project_id, authorization, payload.model_dump())

    @app.post("/api/v1/projects/{project_id}/objects/trace",operation_id="traceObjectEvidence")
    def object_trace(project_id:str,payload:ObjectTraceRequest,authorization:str|None=Header(default=None)):
        return resource("object.trace",project_id,authorization,payload.model_dump())

    @app.get("/api/v1/projects/{project_id}/packages/{package_id}/archive", operation_id="downloadPackageArchive")
    def download_package(project_id: str, package_id: str, authorization: str | None = Header(default=None)):
        principal = service.authenticate(authorization or "")
        if not principal.can("package:export"):
            raise ServiceBoundaryError("FORBIDDEN", "package:export required", status_code=403)
        request = OperationRequest("package.verify", project_id, {"package_id":package_id})
        service.execute(request, principal)
        from kg_mnp.semantic_kernel.packaging.archive import archive_bytes
        from kg_mnp.services.compilation import package_path
        content = archive_bytes(package_path(service._project(request), package_id))
        return Response(content, media_type="application/octet-stream", headers={"Content-Disposition":'attachment; filename="ontology.kgop"'})

    static_root = Path(service.configuration.workbench_root) if service.configuration.workbench_root else Path(__file__).parents[1] / "workbench_static"
    if (static_root / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=static_root / "assets"), name="workbench-assets")

        @app.get("/{spa_path:path}", include_in_schema=False)
        def workbench(spa_path: str):
            if spa_path == "api" or spa_path.startswith(("api/", "health/")):
                return JSONResponse({"error": {"code": "RESOURCE_NOT_FOUND", "message": "resource does not exist"}}, status_code=404)
            return FileResponse(static_root / "index.html", media_type="text/html")
    return app
