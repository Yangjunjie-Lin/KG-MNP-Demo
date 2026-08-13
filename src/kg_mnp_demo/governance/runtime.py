"""Loopback-only human governance HTTP runtime."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from kg_mnp_demo.modeling.dependencies import ROOT

from .authority_binding import (
    GovernanceAuthority,
    _require_verified_production_authority,
)
from .contracts import strict_json_bytes
from .errors import GovernanceError, GovernanceErrorCode
from .security import MAX_BODY_BYTES, csrf_token, exact_fields, proposal_identifier
from .workspace import GovernanceWorkspaceStore

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self'; font-src 'self'; object-src 'none'; frame-src 'none'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'; worker-src 'none'"
)
PAGES = (
    "/",
    "/verification",
    "/diagnostic-inbox",
    "/diagnostic-detail",
    "/create-resolution-proposal",
    "/proposal-review",
    "/approved-amendment-requests",
    "/governance-audit-trail",
)


def create_governance_app(
    store: GovernanceWorkspaceStore,
    *,
    expected_origin: str | None = None,
    web_root: Path | None = None,
    csrf_value: str | None = None,
) -> FastAPI:
    supplied_authority = _require_verified_production_authority(
        store.current_authority()
    )
    if type(store) is not GovernanceWorkspaceStore:
        raise GovernanceError(
            GovernanceErrorCode.AUTHORITY_MISMATCH,
            "production runtime requires the closed production workspace store",
        )
    # Do not retain a caller-controlled store object whose methods could be
    # overridden after startup.  The runtime owns a fresh closed store and a
    # production authority that is reverified by every store load/mutation.
    store = GovernanceWorkspaceStore(store.path, lambda: supplied_authority)
    root = Path(web_root or ROOT / "web" / "governance").resolve(strict=True)
    if not (root / "index.html").is_file():
        raise GovernanceError(GovernanceErrorCode.GOVERNANCE_NOT_READY)
    token = csrf_value or csrf_token()
    app = FastAPI(
        title="KG-MNP Human Governance",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.csrf_token = token

    @app.middleware("http")
    async def security_boundary(request: Request, call_next):
        host = request.headers.get("host", "").split(":", 1)[0]
        if (
            host not in {"127.0.0.1", "testserver"}
            or "x-forwarded-host" in request.headers
            or "forwarded" in request.headers
            or request.headers.get("upgrade", "").casefold() == "websocket"
        ):
            error = GovernanceError(GovernanceErrorCode.ORIGIN_REJECTED)
            return JSONResponse(error.to_dict(), status_code=error.http_status)
        if request.method not in {"GET", "HEAD", "POST"}:
            error = GovernanceError(GovernanceErrorCode.METHOD_NOT_ALLOWED)
            return JSONResponse(error.to_dict(), status_code=error.http_status)
        if request.method == "POST":
            origin = request.headers.get("origin")
            same_origin = expected_origin or f"http://{request.headers.get('host', '')}"
            if origin != same_origin:
                error = GovernanceError(GovernanceErrorCode.ORIGIN_REJECTED)
                return JSONResponse(error.to_dict(), status_code=error.http_status)
            if request.headers.get("x-csrf-token") != token:
                error = GovernanceError(GovernanceErrorCode.CSRF_REJECTED)
                return JSONResponse(error.to_dict(), status_code=error.http_status)
            content_type = request.headers.get("content-type", "")
            if content_type.casefold() != "application/json":
                error = GovernanceError(GovernanceErrorCode.CONTENT_TYPE_REJECTED)
                return JSONResponse(error.to_dict(), status_code=error.http_status)
            declared = request.headers.get("content-length")
            if declared is not None:
                try:
                    if int(declared) > MAX_BODY_BYTES:
                        raise GovernanceError(GovernanceErrorCode.BODY_TOO_LARGE)
                except GovernanceError as error:
                    return JSONResponse(error.to_dict(), status_code=error.http_status)
                except ValueError:
                    error = GovernanceError(GovernanceErrorCode.INVALID_REQUEST)
                    return JSONResponse(error.to_dict(), status_code=error.http_status)
            body = await request.body()
            if len(body) > MAX_BODY_BYTES:
                error = GovernanceError(GovernanceErrorCode.BODY_TOO_LARGE)
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

    @app.exception_handler(GovernanceError)
    async def governance_error(_request: Request, exc: GovernanceError):
        return JSONResponse(exc.to_dict(), status_code=exc.http_status)

    @app.exception_handler(StarletteHTTPException)
    async def route_error(_request: Request, exc: StarletteHTTPException):
        code = (
            GovernanceErrorCode.METHOD_NOT_ALLOWED
            if exc.status_code == 405
            else GovernanceErrorCode.INVALID_REQUEST
        )
        error = GovernanceError(code)
        return JSONResponse(error.to_dict(), status_code=error.http_status)

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        error = GovernanceError(GovernanceErrorCode.GOVERNANCE_NOT_READY)
        return JSONResponse(error.to_dict(), status_code=500)

    def authority() -> GovernanceAuthority:
        return _require_verified_production_authority(store.current_authority())

    def proposal_id(digest: str) -> str:
        return proposal_identifier(digest)

    async def strict_body(request: Request):
        try:
            return strict_json_bytes(await request.body())
        except (ValueError, TypeError) as exc:
            raise GovernanceError(
                GovernanceErrorCode.INVALID_REQUEST,
                "invalid strict JSON request body",
            ) from exc

    def page():
        store.load()
        return FileResponse(root / "index.html", media_type="text/html")

    for route in PAGES:
        app.add_api_route(route, page, methods=["GET", "HEAD"], include_in_schema=False)

    @app.api_route("/assets/app.js", methods=["GET", "HEAD"])
    def javascript():
        return FileResponse(root / "assets" / "app.js", media_type="text/javascript")

    @app.api_route("/assets/styles.css", methods=["GET", "HEAD"])
    def styles():
        return FileResponse(root / "assets" / "styles.css", media_type="text/css")

    @app.api_route("/governance/api/bootstrap", methods=["GET", "HEAD"])
    def bootstrap():
        workspace = store.load()
        return {
            "contract_version": "1.0",
            "csrf_token": token,
            "csrf_token_authority": "ANTI_CSRF_ONLY_NOT_AUTHENTICATED_IDENTITY",
            "workspace_revision": workspace.value["workspace_revision"],
            "head_event_hash": workspace.value["head_event_hash"],
            "status": "GOVERNANCE_READY",
        }

    @app.api_route("/governance/api/status", methods=["GET", "HEAD"])
    def status():
        workspace = store.load()
        current = authority()
        return {
            "contract_version": "1.0",
            **current.binding,
            "workspace_id": workspace.value["workspace_id"],
            "workspace_revision": workspace.value["workspace_revision"],
            "head_event_hash": workspace.value["head_event_hash"],
            "semantic_authority": "NON_AUTHORITATIVE_FUTURE_AMENDMENT_GOVERNANCE_ONLY",
            "status": "GOVERNANCE_READY",
        }

    @app.api_route("/governance/api/diagnostics", methods=["GET", "HEAD"])
    def diagnostics():
        current = authority()
        return {"contract_version": "1.0", "issues": list(current.issues.values())}

    @app.api_route("/governance/api/workspace", methods=["GET", "HEAD"])
    def workspace_state():
        workspace = store.load()
        return {**workspace.reconstruct(), "events": workspace.value["events"]}

    @app.post("/governance/api/proposals", status_code=201)
    async def create_proposal(request: Request):
        body = exact_fields(
            await strict_body(request),
            {
                "expected_workspace_revision",
                "expected_head_hash",
                "target_diagnostic_id",
                "target_diagnostic_basis_hash",
                "proposal_type",
                "proposed_payload",
                "rationale",
                "created_by_label",
                "proposal_revision",
            },
            "proposal request",
        )
        return store.mutate(lambda workspace: workspace.create_proposal(**body))

    @app.post("/governance/api/proposals/{proposal_digest}/submit")
    async def submit(proposal_digest: str, request: Request):
        body = exact_fields(
            await strict_body(request),
            {"expected_workspace_revision", "expected_head_hash"},
            "submit request",
        )
        return store.mutate(
            lambda workspace: workspace.submit_proposal(
                proposal_id(proposal_digest), **body
            )
        )

    @app.post("/governance/api/proposals/{proposal_digest}/review")
    async def review(proposal_digest: str, request: Request):
        body = exact_fields(
            await strict_body(request),
            {
                "expected_workspace_revision",
                "expected_head_hash",
                "decision",
                "review_note",
                "reviewed_by_label",
                "explicit_human_action",
            },
            "review request",
        )
        return store.mutate(
            lambda workspace: workspace.review_proposal(
                proposal_id(proposal_digest), **body
            )
        )

    return app


create_app = create_governance_app
