"""Loopback-only Phase 02 HTTP runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from kg_mnp_demo.modeling.dependencies import ROOT

from .binding import WorkbenchBinding
from .errors import WorkbenchError, WorkbenchErrorCode
from .manifest import validate_workbench_package
from .relay import Phase01Relay
from .view_model import build_view_model


CSP = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "connect-src 'self'",
        "img-src 'self'",
        "font-src 'self'",
        "object-src 'none'",
        "frame-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
        "worker-src 'none'",
    )
)
PAGE_ROUTES = ("/", "/ontology", "/entity", "/fact", "/trace", "/review")


def _parameter_object(
    object_type: str,
    object_value: str,
    datatype_iri: str | None,
    language: str | None,
) -> dict[str, str | None]:
    if object_type == "IRI":
        if datatype_iri is not None or language is not None:
            raise WorkbenchError(WorkbenchErrorCode.INVALID_REQUEST)
        return {"object_type": "IRI", "object_value": object_value}
    if object_type != "LITERAL":
        raise WorkbenchError(WorkbenchErrorCode.INVALID_REQUEST)
    result: dict[str, str | None] = {
        "object_type": "LITERAL",
        "object_value": object_value,
    }
    if datatype_iri is not None:
        result["datatype_iri"] = datatype_iri
    if language is not None:
        result["language"] = language
    return result


def _binding_term(row: dict[str, Any], variable: str) -> dict[str, Any] | None:
    return next(
        (
            binding["term"]
            for binding in row.get("bindings", [])
            if binding.get("variable") == variable
        ),
        None,
    )


def _ontology_version(relay: Phase01Relay) -> str:
    classes = relay.query(
        "/api/v1/ontology/classes",
        {"limit": 1, "offset": 0},
    )
    if not classes["results"]:
        raise WorkbenchError(WorkbenchErrorCode.WORKBENCH_NOT_READY)
    term = _binding_term(classes["results"][0], "term")
    if not term or term.get("term_type") != "IRI":
        raise WorkbenchError(WorkbenchErrorCode.WORKBENCH_NOT_READY)
    details = relay.query(
        "/api/v1/ontology/term",
        {"iri": term["iri"], "limit": 100, "offset": 0},
    )
    for row in details["results"]:
        version = _binding_term(row, "ontologyVersion")
        if version and version.get("term_type") == "IRI":
            return str(version["iri"])
    raise WorkbenchError(WorkbenchErrorCode.WORKBENCH_NOT_READY)


def create_workbench_app(
    *,
    binding: WorkbenchBinding,
    relay: Phase01Relay,
    package_directory: Path | None = None,
) -> FastAPI:
    """Create a fail-closed same-origin server bound to verified Phase 01."""

    web_root = Path(package_directory or ROOT / "web" / "workbench")
    manifest: dict[str, Any] | None = None
    if package_directory is not None:
        manifest = validate_workbench_package(web_root, binding)
    binding.verify_health(relay.health())
    ontology_version = _ontology_version(relay)
    app = FastAPI(
        title="KG-MNP Read-Only Evidence Workbench",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.binding = binding
    app.state.relay = relay
    app.state.ontology_version = ontology_version

    @app.middleware("http")
    async def security_boundary(request: Request, call_next):
        host = request.headers.get("host", "").split(":", 1)[0]
        if (
            host not in {"127.0.0.1", "testserver"}
            or "x-forwarded-host" in request.headers
            or "forwarded" in request.headers
            or request.headers.get("upgrade", "").casefold() == "websocket"
        ):
            error = WorkbenchError(WorkbenchErrorCode.RELAY_ROUTE_FORBIDDEN)
            return JSONResponse(error.to_dict(), status_code=error.http_status)
        if request.method not in {"GET", "HEAD"}:
            error = WorkbenchError(
                WorkbenchErrorCode.READ_ONLY_POLICY_VIOLATION
            )
            return JSONResponse(error.to_dict(), status_code=error.http_status)
        length = request.headers.get("content-length")
        if length:
            try:
                body_size = int(length)
            except ValueError:
                body_size = 1
            if body_size != 0:
                error = WorkbenchError(
                    WorkbenchErrorCode.READ_ONLY_POLICY_VIOLATION
                )
                return JSONResponse(
                    error.to_dict(),
                    status_code=error.http_status,
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        return response

    @app.exception_handler(WorkbenchError)
    async def workbench_error(_request: Request, exc: WorkbenchError):
        return JSONResponse(exc.to_dict(), status_code=exc.http_status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        error = WorkbenchError(WorkbenchErrorCode.INVALID_REQUEST)
        return JSONResponse(error.to_dict(), status_code=error.http_status)

    @app.exception_handler(StarletteHTTPException)
    async def route_error(_request: Request, _exc: StarletteHTTPException):
        error = WorkbenchError(WorkbenchErrorCode.RELAY_ROUTE_FORBIDDEN)
        return JSONResponse(error.to_dict(), status_code=error.http_status)

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        error = WorkbenchError(WorkbenchErrorCode.INTERNAL_ERROR)
        return JSONResponse(error.to_dict(), status_code=500)

    def page_response() -> FileResponse:
        return FileResponse(web_root / "index.html", media_type="text/html")

    for page_route in PAGE_ROUTES:
        app.add_api_route(
            page_route,
            page_response,
            methods=["GET", "HEAD"],
            include_in_schema=False,
        )

    @app.api_route("/assets/app.js", methods=["GET", "HEAD"])
    def app_javascript():
        return FileResponse(
            web_root / "assets" / "app.js",
            media_type="text/javascript",
        )

    @app.api_route("/assets/styles.css", methods=["GET", "HEAD"])
    def app_styles():
        return FileResponse(
            web_root / "assets" / "styles.css",
            media_type="text/css",
        )

    @app.get("/workbench/api/status")
    def status():
        binding.verify_health(relay.health())
        return {
            "contract_version": "1.0",
            **binding.public_status(),
            "ontology_version": ontology_version,
            "frontend_build_hash": (
                manifest["frontend_build_hash"] if manifest else None
            ),
            "status": "WORKBENCH_READY",
        }

    def view(
        path: str,
        parameters: dict[str, Any],
        view_type: str,
    ) -> dict[str, Any]:
        result = relay.query(path, parameters)
        return build_view_model(result, view_type=view_type)

    @app.get("/workbench/api/view/ontology/classes")
    def ontology_classes(
        limit: int = Query(100, ge=1, le=999),
        offset: int = Query(0, ge=0, le=1_000_000),
    ):
        return view(
            "/api/v1/ontology/classes",
            {"limit": limit, "offset": offset},
            "ONTOLOGY",
        )

    @app.get("/workbench/api/view/ontology/properties")
    def ontology_properties(
        limit: int = Query(100, ge=1, le=999),
        offset: int = Query(0, ge=0, le=1_000_000),
    ):
        return view(
            "/api/v1/ontology/properties",
            {"limit": limit, "offset": offset},
            "ONTOLOGY",
        )

    @app.get("/workbench/api/view/ontology/term")
    def ontology_term(
        iri: str = Query(..., max_length=2048),
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0, le=1_000_000),
    ):
        return view(
            "/api/v1/ontology/term",
            {"iri": iri, "limit": limit, "offset": offset},
            "ONTOLOGY",
        )

    @app.get("/workbench/api/view/entity")
    def entity(
        iri: str = Query(..., max_length=2048),
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0, le=1_000_000),
    ):
        return view(
            "/api/v1/entity",
            {"iri": iri, "limit": limit, "offset": offset},
            "ENTITY",
        )

    @app.get("/workbench/api/view/fact")
    def fact(
        subject: str = Query(..., max_length=2048),
        predicate: str = Query(..., max_length=2048),
        object_type: str = Query(..., pattern="^(IRI|LITERAL)$"),
        object_value: str = Query(..., max_length=4096),
        datatype_iri: str | None = Query(None, max_length=2048),
        language: str | None = Query(None, max_length=64),
    ):
        parameters: dict[str, Any] = {
            "subject": subject,
            "predicate": predicate,
            **_parameter_object(
                object_type,
                object_value,
                datatype_iri,
                language,
            ),
        }
        return view("/api/v1/fact", parameters, "FACT")

    @app.get("/workbench/api/view/fact/provenance")
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
        parameters: dict[str, Any] = {
            "subject": subject,
            "predicate": predicate,
            **_parameter_object(
                object_type,
                object_value,
                datatype_iri,
                language,
            ),
            "limit": limit,
            "offset": offset,
        }
        return view(
            "/api/v1/fact/provenance",
            parameters,
            "FACT_TRACE",
        )

    @app.get("/workbench/api/view/review")
    def review(
        resource_id: str = Query(..., max_length=2048),
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0, le=1_000_000),
    ):
        return view(
            "/api/v1/review-trace",
            {"resource_id": resource_id, "limit": limit, "offset": offset},
            "REVIEW_TRACE",
        )

    @app.get("/workbench/api/view/source")
    def source(
        source_ref: str = Query(..., max_length=2048),
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0, le=1_000_000),
    ):
        return view(
            "/api/v1/source-trace",
            {"source_ref": source_ref, "limit": limit, "offset": offset},
            "SOURCE_TRACE",
        )

    @app.get("/workbench/api/view/evidence")
    def evidence(
        evidence_ref: str = Query(..., max_length=2048),
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0, le=1_000_000),
    ):
        return view(
            "/api/v1/evidence-trace",
            {"evidence_ref": evidence_ref, "limit": limit, "offset": offset},
            "EVIDENCE_TRACE",
        )

    @app.get("/workbench/api/view/trace")
    def trace(
        resource_id: str = Query(..., max_length=2048),
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0, le=1_000_000),
    ):
        return view(
            "/api/v1/trace",
            {"resource_id": resource_id, "limit": limit, "offset": offset},
            "CROSS_TRACE",
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def no_favicon():
        return Response(status_code=204)

    return app
