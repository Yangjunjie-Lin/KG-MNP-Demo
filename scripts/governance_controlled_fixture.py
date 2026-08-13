"""TEST-ONLY Phase04 diagnostics for governance behavior and security probes.

This module is deliberately an integration fixture below ``scripts/``. A
controlled fixture is not a verified Phase03 artifact and does not carry a
Phase03 attestation. The only conversion to ``GovernanceAuthority`` is the
explicitly named test-harness adapter at the bottom of this file.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from kg_mnp_demo.diagnostics.authority_binding import AuthorityBindings
from kg_mnp_demo.diagnostics.engine import reconstruct_diagnostics
from kg_mnp_demo.diagnostics.issue import diagnostic_semantic_basis
from kg_mnp_demo.diagnostics.policy import diagnostic_policy_hash
from kg_mnp_demo.governance.authority_binding import GovernanceAuthority
from kg_mnp_demo.governance.contracts import strict_json_bytes, strict_json_file
from kg_mnp_demo.governance.errors import GovernanceError, GovernanceErrorCode
from kg_mnp_demo.governance.identity import CONTROLLED_FIXTURE_NAMESPACE
from kg_mnp_demo.governance.runtime import CSP, PAGES
from kg_mnp_demo.governance.security import (
    MAX_BODY_BYTES,
    csrf_token,
    exact_fields,
    proposal_identifier,
)
from kg_mnp_demo.governance.workspace import (
    GovernanceWorkspace,
    GovernanceWorkspaceStore,
    _workspace_value,
)
from kg_mnp_demo.modeling.canonical_json import semantic_hash
from kg_mnp_demo.modeling.dependencies import ROOT

FIXTURE_NAMESPACE = CONTROLLED_FIXTURE_NAMESPACE
FIXTURE_TYPE = "PHASE04_CONTROLLED_DIAGNOSTIC_FIXTURE"
FIXTURE_STATUS = "CONTROLLED_DIAGNOSTIC_FIXTURE"


def _fixture_hash(label: str) -> str:
    return semantic_hash({"phase": "Application Phase04", "test_fixture": label})


def _fixture_bindings() -> AuthorityBindings:
    publication_hash = _fixture_hash("publication")
    return AuthorityBindings(
        # Phase03's frozen schema requires this structural publication-ID shape
        # during this private reconstruction step. It is never exposed: the
        # fixture projection below rewrites it into the Phase04 test namespace.
        publication_id=f"urn:kg-mnp:test-fixture:{publication_hash}",
        publication_semantic_hash=publication_hash,
        phase01_attestation_hash=_fixture_hash("not-a-phase01-attestation"),
        phase02_attestation_hash=_fixture_hash("not-a-phase02-attestation"),
        query_registry_hash=_fixture_hash("query-registry"),
        repository_semantic_hash=_fixture_hash("repository"),
        diagnostic_policy_hash=diagnostic_policy_hash(),
    )


def _controlled_snapshot(bindings: AuthorityBindings) -> dict[str, Any]:
    """Return synthetic inputs, never an authority snapshot trusted by production."""

    def iri(value: str) -> str:
        return f"{FIXTURE_NAMESPACE}{value}"

    def requirement(name: str, *, maximum: int | None = 1) -> dict[str, Any]:
        focus = iri(f"focus:{name}")
        if name == "missing":
            focus += ":<img src=x onerror=window.__xss=1>"
        constraint = iri(f"constraint:{name}")
        return {
            "focus_node": focus,
            "path": iri("property:controlled"),
            "requirement_type": "CONTROLLED_SHACL_MIN_MAX_COUNT",
            "authority_iri": constraint,
            "shape_iri": iri(f"shape:{name}"),
            "constraint_iri": constraint,
            "module": "phase04-controlled-test-fixture",
            "publication_id": bindings.publication_id,
            "min_count": 1,
            "max_count": maximum,
        }

    conflict_focus = iri("focus:conflict")
    rejected_focus = iri("focus:rejected")
    predicate = iri("property:controlled")
    return {
        "authority_bindings": bindings.to_dict(),
        "requirements": [
            requirement("missing"),
            requirement("rejected"),
            requirement("conflict"),
        ],
        "facts": [
            {
                "subject": conflict_focus,
                "predicate": predicate,
                "object": "confirmed-a",
                "assertion_ref": iri("assertion:confirmed-a"),
            },
            {
                "subject": conflict_focus,
                "predicate": predicate,
                "object": "confirmed-b",
                "assertion_ref": iri("assertion:confirmed-b"),
            },
        ],
        "constraint_results": [],
        "candidates": [
            {
                "focus_node": rejected_focus,
                "path": predicate,
                "value": "rejected-value",
                "outcome": "REJECT",
                "candidate_ref": iri("candidate:rejected"),
                "review_decision_ref": iri("decision:rejected"),
                "evidence_refs": [],
                "source_refs": [],
            }
        ],
        "conflict_rules": [],
    }


def _assert_fixture_namespace(snapshot: Mapping[str, Any]) -> None:
    """Keep every caller-minted IRI in the unmistakable test namespace."""

    iri_fields = {
        "publication_id",
        "focus_node",
        "path",
        "authority_iri",
        "shape_iri",
        "constraint_iri",
        "assertion_ref",
        "candidate_ref",
        "review_decision_ref",
    }

    def visit(value: Any, field: str | None = None) -> None:
        if (
            field in iri_fields
            and value is not None
            and (
                not isinstance(value, str)
                or not value.startswith(FIXTURE_NAMESPACE)
            )
        ):
            raise ValueError(
                f"controlled fixture IRI escaped test namespace: {field}"
            )
        if isinstance(value, Mapping):
            for key, child in value.items():
                visit(child, str(key))
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child, field)

    visit(snapshot)


def _as_controlled_fixture_package(package: Mapping[str, Any]) -> dict[str, Any]:
    """Re-namespace engine output so it cannot pass as a Phase03 package."""

    value = deepcopy(dict(package))
    original_publication_id = value["authority_bindings"]["publication_id"]
    fixture_publication_id = (
        f"{FIXTURE_NAMESPACE}publication:"
        f"{value['authority_bindings']['publication_semantic_hash']}"
    )
    value["authority_bindings"]["publication_id"] = fixture_publication_id
    for issue in value["issues"]:
        issue["publication_id"] = fixture_publication_id
        for basis in issue["authority_basis"]:
            if basis.get("publication_id") == original_publication_id:
                basis["publication_id"] = fixture_publication_id
        basis_hash = semantic_hash(diagnostic_semantic_basis(issue))
        issue["diagnostic_basis_hash"] = basis_hash
        issue["diagnostic_id"] = f"{FIXTURE_NAMESPACE}diagnostic:{basis_hash}"
    value["manifest"]["issue_ids"] = [
        issue["diagnostic_id"] for issue in value["issues"]
    ]
    value["manifest"].pop("package_id", None)
    value["manifest"].pop("package_semantic_hash", None)
    value["manifest"]["status"] = FIXTURE_STATUS
    value["status"] = FIXTURE_STATUS
    fixture_package_hash = semantic_hash(value)
    value["manifest"]["fixture_package_id"] = (
        f"{FIXTURE_NAMESPACE}diagnostic-package:{fixture_package_hash}"
    )
    value["manifest"]["controlled_fixture_diagnostic_package_hash"] = (
        fixture_package_hash
    )
    return value


@dataclass(frozen=True)
class ControlledDiagnosticFixture:
    """Synthetic diagnostic evidence carrying non-production identity markers."""

    _authority_snapshot: Mapping[str, Any]
    _diagnostic_package: Mapping[str, Any]

    @classmethod
    def create(cls) -> ControlledDiagnosticFixture:
        snapshot = _controlled_snapshot(_fixture_bindings())
        package = _as_controlled_fixture_package(
            reconstruct_diagnostics(snapshot).to_dict()
        )
        fixture_publication_id = package["authority_bindings"]["publication_id"]
        snapshot["authority_bindings"]["publication_id"] = fixture_publication_id
        for collection in ("requirements", "conflict_rules"):
            for row in snapshot[collection]:
                row["publication_id"] = fixture_publication_id
        _assert_fixture_namespace(snapshot)
        return cls(
            _authority_snapshot=deepcopy(snapshot),
            _diagnostic_package=deepcopy(package),
        )

    @property
    def fixture_type(self) -> str:
        return FIXTURE_TYPE

    @property
    def status(self) -> str:
        return FIXTURE_STATUS

    @property
    def production_authority(self) -> bool:
        return False

    @property
    def test_only(self) -> bool:
        return True

    @property
    def authority_snapshot(self) -> dict[str, Any]:
        return deepcopy(dict(self._authority_snapshot))

    @property
    def diagnostic_package(self) -> dict[str, Any]:
        return deepcopy(dict(self._diagnostic_package))

    @property
    def controlled_fixture_diagnostic_package_hash(self) -> str:
        return str(
            self._diagnostic_package["manifest"][
                "controlled_fixture_diagnostic_package_hash"
            ]
        )

    def _semantic_content(self) -> dict[str, Any]:
        return {
            "contract_version": "1.0",
            "fixture_type": self.fixture_type,
            "status": self.status,
            "production_authority": self.production_authority,
            "test_only": self.test_only,
            "authority_snapshot": self.authority_snapshot,
            "diagnostic_package": self.diagnostic_package,
            "controlled_fixture_diagnostic_package_hash": (
                self.controlled_fixture_diagnostic_package_hash
            ),
        }

    @property
    def controlled_fixture_hash(self) -> str:
        return semantic_hash(self._semantic_content())

    @property
    def fixture_id(self) -> str:
        return f"{FIXTURE_NAMESPACE}fixture:{self.controlled_fixture_hash}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._semantic_content(),
            "fixture_id": self.fixture_id,
            "controlled_fixture_hash": self.controlled_fixture_hash,
        }


def controlled_governance_authority_for_test_harness(
    fixture: ControlledDiagnosticFixture,
) -> GovernanceAuthority:
    """Adapt a marked fixture solely for Phase04 behavioral tests.

    No Phase03 attestation is built or claimed.  The placeholder physical hash
    is derived from the marked fixture and is meaningful only inside this test
    harness.
    """

    if (
        fixture.fixture_type != FIXTURE_TYPE
        or fixture.status != FIXTURE_STATUS
        or fixture.production_authority
        or not fixture.test_only
    ):
        raise ValueError("unmarked controlled fixture")
    package = fixture.diagnostic_package
    bindings = package["authority_bindings"]
    issues: dict[str, dict[str, Any]] = {}
    for fixture_issue in package["issues"]:
        issue = deepcopy(fixture_issue)
        issues[issue["diagnostic_id"]] = issue
    return GovernanceAuthority(
        authority_type="CONTROLLED_TEST_HARNESS",
        publication_id=bindings["publication_id"],
        publication_semantic_hash=bindings["publication_semantic_hash"],
        repository_semantic_hash=bindings["repository_semantic_hash"],
        upstream_phase03_attestation_sha256=semantic_hash(
            {
                "test_only": True,
                "controlled_fixture_hash": fixture.controlled_fixture_hash,
                "status": FIXTURE_STATUS,
            }
        ),
        upstream_phase03_diagnostic_package_hash=(
            fixture.controlled_fixture_diagnostic_package_hash
        ),
        issues=issues,
    )


def controlled_governance_workspace_for_test_harness(
    authority: GovernanceAuthority,
    current_authority=None,
) -> GovernanceWorkspace:
    """Create an in-memory workspace through the explicit TEST-ONLY harness."""

    if authority.authority_type != "CONTROLLED_TEST_HARNESS":
        raise ValueError("controlled authority required")
    return ControlledGovernanceWorkspaceForTestHarness(
        _workspace_value(authority), current_authority or (lambda: authority)
    )


class ControlledGovernanceWorkspaceForTestHarness(GovernanceWorkspace):
    """TEST-ONLY adapter over the shared governance state-machine logic."""

    def _require_current_authority_mode(self) -> GovernanceAuthority:
        authority = self.current_authority()
        mode = self.value.get("authority_binding", {}).get("authority_type")
        if (
            mode != "CONTROLLED_TEST_HARNESS"
            or authority.authority_type != "CONTROLLED_TEST_HARNESS"
        ):
            raise GovernanceError(GovernanceErrorCode.AUTHORITY_MISMATCH)
        return authority


class ControlledGovernanceWorkspaceStoreForTestHarness(GovernanceWorkspaceStore):
    """TEST-ONLY persistence adapter, outside the production package."""

    def _validate_authority(
        self, authority: GovernanceAuthority
    ) -> GovernanceAuthority:
        if authority.authority_type != "CONTROLLED_TEST_HARNESS":
            raise GovernanceError(GovernanceErrorCode.AUTHORITY_MISMATCH)
        return authority

    def initialize(self, authority: GovernanceAuthority) -> GovernanceWorkspace:
        with self._lock:
            self._validate_authority(authority)
            if self.path.exists():
                raise GovernanceError(
                    GovernanceErrorCode.REPLAY_DETECTED, "workspace already exists"
                )
            workspace = controlled_governance_workspace_for_test_harness(
                authority, self.current_authority
            )
            self._persist(workspace.value)
            return workspace

    def load(self) -> GovernanceWorkspace:
        with self._lock:
            self._validate_authority(self.current_authority())
            self._assert_safe_path(for_write=False)
            workspace = ControlledGovernanceWorkspaceForTestHarness(
                strict_json_file(self.path), self.current_authority
            )
            workspace.reconstruct()
            return workspace


def controlled_governance_store_for_test_harness(
    path,
    current_authority: Callable[[], GovernanceAuthority],
) -> ControlledGovernanceWorkspaceStoreForTestHarness:
    """Create a store that is unreachable from the production runtime API."""

    if current_authority().authority_type != "CONTROLLED_TEST_HARNESS":
        raise ValueError("controlled authority required")
    return ControlledGovernanceWorkspaceStoreForTestHarness(
        path, current_authority
    )


def controlled_governance_app_for_test_harness(
    store: ControlledGovernanceWorkspaceStoreForTestHarness,
    *,
    expected_origin: str | None = None,
    web_root: Path | None = None,
    csrf_value: str | None = None,
) -> FastAPI:
    """Serve TEST-ONLY probes without importing a production app factory."""

    if type(store) is not ControlledGovernanceWorkspaceStoreForTestHarness:
        raise ValueError("controlled store required")
    if store.current_authority().authority_type != "CONTROLLED_TEST_HARNESS":
        raise ValueError("controlled authority required")
    root = Path(web_root or ROOT / "web" / "governance").resolve(strict=True)
    if not (root / "index.html").is_file():
        raise GovernanceError(GovernanceErrorCode.GOVERNANCE_NOT_READY)
    token = csrf_value or csrf_token()
    app = FastAPI(
        title="KG-MNP Controlled Governance Test Harness",
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
            if request.headers.get("content-type", "").casefold() != "application/json":
                error = GovernanceError(GovernanceErrorCode.CONTENT_TYPE_REJECTED)
                return JSONResponse(error.to_dict(), status_code=error.http_status)
            declared = request.headers.get("content-length")
            try:
                if declared is not None and int(declared) > MAX_BODY_BYTES:
                    raise GovernanceError(GovernanceErrorCode.BODY_TOO_LARGE)
            except GovernanceError as error:
                return JSONResponse(error.to_dict(), status_code=error.http_status)
            except ValueError:
                error = GovernanceError(GovernanceErrorCode.INVALID_REQUEST)
                return JSONResponse(error.to_dict(), status_code=error.http_status)
            if len(await request.body()) > MAX_BODY_BYTES:
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
        current = store.current_authority()
        store._validate_authority(current)
        return current

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
        return {"contract_version": "1.0", "issues": list(authority().issues.values())}

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
        proposal_id = proposal_identifier(
            proposal_digest, controlled_test_harness=True
        )
        return store.mutate(
            lambda workspace: workspace.submit_proposal(proposal_id, **body)
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
        proposal_id = proposal_identifier(
            proposal_digest, controlled_test_harness=True
        )
        return store.mutate(
            lambda workspace: workspace.review_proposal(proposal_id, **body)
        )

    return app
