"""Loopback-only, read-only inspection runtime for a validated package."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from kg_mnp_demo.modeling.dependencies import ROOT

from .authority_binding import AuthorityBindings
from .errors import DiagnosticError, DiagnosticErrorCode
from .validator import validate_diagnostic_package

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "connect-src 'self'; "
    "img-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "frame-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'; "
    "worker-src 'none'"
)
PAGE_ROUTES = (
    "/",
    "/verification",
    "/summary",
    "/missing",
    "/constraints",
    "/conflicts",
    "/lineage-gaps",
    "/diagnostic",
)


def create_diagnostics_app(
    package: Mapping[str, Any] | Path | str,
    *,
    authority_status: Callable[[], Mapping[str, Any]] | None = None,
    web_root: Path | None = None,
) -> FastAPI:
    validated = validate_diagnostic_package(package)
    bindings = AuthorityBindings.from_dict(validated["authority_bindings"])
    root = Path(web_root or ROOT / "web" / "diagnostics")
    if not (root / "index.html").is_file():
        raise DiagnosticError(DiagnosticErrorCode.DIAGNOSTICS_NOT_READY)

    app = FastAPI(
        title="KG-MNP Deterministic Diagnostics",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.package = validated

    def verify_current_authority() -> None:
        if authority_status is not None:
            bindings.verify_runtime_identity(authority_status())

    @app.middleware("http")
    async def security_boundary(request: Request, call_next):
        host = request.headers.get("host", "").split(":", 1)[0]
        if (
            host not in {"127.0.0.1", "testserver"}
            or "x-forwarded-host" in request.headers
            or "forwarded" in request.headers
            or request.headers.get("upgrade", "").casefold() == "websocket"
        ):
            error = DiagnosticError(DiagnosticErrorCode.INVALID_REQUEST)
            return JSONResponse(error.to_dict(), status_code=error.http_status)
        if request.method not in {"GET", "HEAD"}:
            error = DiagnosticError(
                DiagnosticErrorCode.READ_ONLY_POLICY_VIOLATION
            )
            return JSONResponse(error.to_dict(), status_code=error.http_status)
        if request.headers.get("content-length") not in {None, "0"}:
            error = DiagnosticError(
                DiagnosticErrorCode.READ_ONLY_POLICY_VIOLATION
            )
            return JSONResponse(error.to_dict(), status_code=error.http_status)
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

    @app.exception_handler(DiagnosticError)
    async def diagnostic_error(_request: Request, exc: DiagnosticError):
        return JSONResponse(exc.to_dict(), status_code=exc.http_status)

    @app.exception_handler(StarletteHTTPException)
    async def route_error(_request: Request, _exc: StarletteHTTPException):
        error = DiagnosticError(DiagnosticErrorCode.INVALID_REQUEST)
        return JSONResponse(error.to_dict(), status_code=error.http_status)

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        error = DiagnosticError(DiagnosticErrorCode.DIAGNOSTICS_NOT_READY)
        return JSONResponse(error.to_dict(), status_code=error.http_status)

    def page_response() -> FileResponse:
        verify_current_authority()
        return FileResponse(root / "index.html", media_type="text/html")

    for route in PAGE_ROUTES:
        app.add_api_route(
            route,
            page_response,
            methods=["GET", "HEAD"],
            include_in_schema=False,
        )

    @app.api_route("/assets/app.js", methods=["GET", "HEAD"])
    def javascript():
        return FileResponse(root / "assets" / "app.js", media_type="text/javascript")

    @app.api_route("/assets/styles.css", methods=["GET", "HEAD"])
    def styles():
        return FileResponse(root / "assets" / "styles.css", media_type="text/css")

    @app.api_route("/diagnostics/api/status", methods=["GET", "HEAD"])
    def status():
        verify_current_authority()
        if validated["status"] != "DIAGNOSTICS_VALIDATED":
            raise DiagnosticError(DiagnosticErrorCode.DIAGNOSTICS_NOT_READY)
        return {
            "contract_version": "1.0",
            "package_id": validated["manifest"]["package_id"],
            "package_semantic_hash": validated["manifest"]["package_semantic_hash"],
            "publication_id": bindings.publication_id,
            "repository_semantic_hash": bindings.repository_semantic_hash,
            "semantic_authority": "DERIVED_DIAGNOSTIC_OBSERVATION_ONLY",
            "read_only": True,
            "status": "DIAGNOSTICS_READY",
        }

    @app.api_route("/diagnostics/api/summary", methods=["GET", "HEAD"])
    def summary():
        verify_current_authority()
        return {
            "contract_version": "1.0",
            "summary": validated["summary"],
            "coverage": validated["coverage"],
        }

    @app.api_route("/diagnostics/api/issues", methods=["GET", "HEAD"])
    def issues(
        classification: str | None = Query(default=None, max_length=64),
        scope: str | None = Query(default=None, max_length=64),
        focus_node: str | None = Query(default=None, max_length=2048),
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ):
        verify_current_authority()
        rows = validated["issues"]
        if classification is not None:
            rows = [row for row in rows if row["classification"] == classification]
        if scope is not None:
            rows = [row for row in rows if row["scope"] == scope]
        if focus_node is not None:
            rows = [row for row in rows if row["focus_node"] == focus_node]
        return {
            "contract_version": "1.0",
            "issues": rows[offset : offset + limit],
            "result_count": len(rows),
            "offset": offset,
            "limit": limit,
        }

    @app.api_route(
        "/diagnostics/api/issues/{diagnostic_id}",
        methods=["GET", "HEAD"],
    )
    def detail(diagnostic_id: str):
        verify_current_authority()
        identifier = f"urn:kg-mnp:diagnostic:{diagnostic_id}"
        if len(diagnostic_id) != 64 or any(
            value not in "0123456789abcdef" for value in diagnostic_id
        ):
            raise DiagnosticError(DiagnosticErrorCode.INVALID_REQUEST)
        row = next(
            (issue for issue in validated["issues"] if issue["diagnostic_id"] == identifier),
            None,
        )
        if row is None:
            raise DiagnosticError(DiagnosticErrorCode.INVALID_REQUEST)
        return row

    return app


create_app = create_diagnostics_app
