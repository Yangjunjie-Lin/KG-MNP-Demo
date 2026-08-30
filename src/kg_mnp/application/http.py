"""Local-only FastAPI projection for registered read-only queries."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .errors import ApplicationError, ErrorCode
from .policy import MAX_REQUEST_BODY_BYTES, MAX_RESPONSE_BODY_BYTES
from .service import ApplicationService


def _object_parameter(
    *,
    object_type: str,
    object_value: str,
    datatype_iri: str | None,
    language: str | None,
) -> dict[str, Any]:
    if object_type == "IRI":
        if datatype_iri is not None or language is not None:
            raise ApplicationError(ErrorCode.INVALID_PARAMETER)
        return {"term_type": "IRI", "value": object_value}
    if object_type != "LITERAL":
        raise ApplicationError(ErrorCode.INVALID_PARAMETER)
    return {
        "term_type": "LITERAL",
        "value": object_value,
        "datatype_iri": datatype_iri,
        "language": language,
    }


def create_app(service: ApplicationService) -> FastAPI:
    readiness = service.runtime_check()
    if readiness.get("status") != "APPLICATION_READY":
        raise ApplicationError(ErrorCode.APPLICATION_NOT_READY)
    app = FastAPI(
        title="KG-MNP Read-Only Semantic Application",
        version="1.0.0",
        description="Read-only projection bound to a verified Foundation publication.",
    )
    app.state.startup_readiness = readiness

    @app.middleware("http")
    async def readonly_limits(request: Request, call_next):
        if request.method not in {"GET", "HEAD"}:
            error = ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
            return JSONResponse(error.to_dict(), status_code=error.http_status)
        length = request.headers.get("content-length")
        if length:
            try:
                size = int(length)
            except ValueError:
                size = MAX_REQUEST_BODY_BYTES + 1
            if size > MAX_REQUEST_BODY_BYTES or size > 0:
                error = ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
                return JSONResponse(error.to_dict(), status_code=error.http_status)
        response = await call_next(request)
        response_length = response.headers.get("content-length")
        if response_length and int(response_length) > MAX_RESPONSE_BODY_BYTES:
            error = ApplicationError(ErrorCode.RESULT_LIMIT_EXCEEDED)
            return JSONResponse(error.to_dict(), status_code=error.http_status)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(ApplicationError)
    async def application_error_handler(_request: Request, exc: ApplicationError):
        return JSONResponse(exc.to_dict(), status_code=exc.http_status)

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(_request: Request, _exc: RequestValidationError):
        error = ApplicationError(ErrorCode.INVALID_PARAMETER)
        return JSONResponse(error.to_dict(), status_code=error.http_status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request: Request, exc: StarletteHTTPException):
        code = ErrorCode.INVALID_QUERY_ID if exc.status_code == 404 else ErrorCode.READ_ONLY_POLICY_VIOLATION
        error = ApplicationError(code)
        return JSONResponse(error.to_dict(), status_code=error.http_status)

    @app.exception_handler(Exception)
    async def internal_error_handler(_request: Request, _exc: Exception):
        error = ApplicationError(ErrorCode.INTERNAL_ERROR)
        return JSONResponse(error.to_dict(), status_code=500)

    @app.get("/api/v1/health")
    def health():
        return service.runtime_check()

    @app.get("/api/v1/entity")
    def entity(
        iri: str = Query(..., max_length=2048),
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0, le=1_000_000),
    ):
        return service.run("business.entity", {"iri": iri, "limit": limit, "offset": offset})

    @app.get("/api/v1/entity/provenance")
    def entity_provenance(
        iri: str = Query(..., max_length=2048),
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0, le=1_000_000),
    ):
        return service.run("provenance.entity", {"iri": iri, "limit": limit, "offset": offset})

    @app.get("/api/v1/fact")
    def fact(
        subject: str = Query(..., max_length=2048),
        predicate: str = Query(..., max_length=2048),
        object_type: str = Query(..., pattern="^(IRI|LITERAL)$"),
        object_value: str = Query(..., max_length=4096),
        datatype_iri: str | None = Query(None, max_length=2048),
        language: str | None = Query(None, max_length=64),
    ):
        return service.run("business.fact", {"subject": subject, "predicate": predicate, "object": _object_parameter(object_type=object_type, object_value=object_value, datatype_iri=datatype_iri, language=language)})

    @app.get("/api/v1/fact/provenance")
    def fact_provenance(
        subject: str = Query(..., max_length=2048),
        predicate: str = Query(..., max_length=2048),
        object_type: str = Query(..., pattern="^(IRI|LITERAL)$"),
        object_value: str = Query(..., max_length=4096),
        datatype_iri: str | None = Query(None, max_length=2048),
        language: str | None = Query(None, max_length=64),
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0, le=1_000_000),
    ):
        return service.run("provenance.fact", {"subject": subject, "predicate": predicate, "object": _object_parameter(object_type=object_type, object_value=object_value, datatype_iri=datatype_iri, language=language), "limit": limit, "offset": offset})

    @app.get("/api/v1/ontology/classes")
    def ontology_classes(limit: int = Query(100, ge=1, le=999), offset: int = Query(0, ge=0, le=1_000_000)):
        return service.run("ontology.classes", {"limit": limit, "offset": offset})

    @app.get("/api/v1/ontology/properties")
    def ontology_properties(limit: int = Query(100, ge=1, le=999), offset: int = Query(0, ge=0, le=1_000_000)):
        return service.run("ontology.properties", {"limit": limit, "offset": offset})

    @app.get("/api/v1/ontology/term")
    def ontology_term(iri: str = Query(..., max_length=2048), limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0, le=1_000_000)):
        return service.run("ontology.term", {"term": iri, "limit": limit, "offset": offset})

    @app.get("/api/v1/review-trace")
    def review_trace(resource_id: str = Query(..., max_length=2048), limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0, le=1_000_000)):
        return service.run("review.trace", {"resource_id": resource_id, "limit": limit, "offset": offset})

    @app.get("/api/v1/source-trace")
    def source_trace(source_ref: str = Query(..., max_length=2048), limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0, le=1_000_000)):
        return service.run("source.trace", {"source_ref": source_ref, "limit": limit, "offset": offset})

    @app.get("/api/v1/evidence-trace")
    def evidence_trace(evidence_ref: str = Query(..., max_length=2048), limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0, le=1_000_000)):
        return service.run("evidence.trace", {"evidence_ref": evidence_ref, "limit": limit, "offset": offset})

    @app.get("/api/v1/trace")
    def cross_trace(resource_id: str = Query(..., max_length=2048), limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0, le=1_000_000)):
        return service.run("trace.resource", {"resource_id": resource_id, "limit": limit, "offset": offset})

    return app
