from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kg_mnp_demo.governance.errors import GovernanceError
from kg_mnp_demo.governance.security import MAX_BODY_BYTES
from kg_mnp_demo.governance.workspace import GovernanceWorkspaceStore
from scripts.governance_controlled_fixture import (
    controlled_governance_app_for_test_harness,
    controlled_governance_store_for_test_harness,
)

from ._helpers import authority, proposal_arguments


def client(tmp_path: Path) -> tuple[TestClient, GovernanceWorkspaceStore]:
    auth = authority()
    store = controlled_governance_store_for_test_harness(
        tmp_path / "governance-workspace.json", lambda: auth
    )
    store.initialize(auth)
    return (
        TestClient(
            controlled_governance_app_for_test_harness(
                store, csrf_value="test-csrf-token"
            )
        ),
        store,
    )


def headers(**extra):
    return {
        "Origin": "http://testserver",
        "X-CSRF-Token": "test-csrf-token",
        "Content-Type": "application/json",
        **extra,
    }


def request_body(auth=None):
    value = {
        "expected_workspace_revision": 0,
        "expected_head_hash": "GENESIS",
        **proposal_arguments(auth or authority()),
    }
    return value


def test_status_bootstrap_and_pages_are_loopback_only(tmp_path: Path) -> None:
    http, _ = client(tmp_path)
    assert (
        http.get("/governance/api/status").json()["semantic_authority"]
        == "NON_AUTHORITATIVE_FUTURE_AMENDMENT_GOVERNANCE_ONLY"
    )
    bootstrap = http.get("/governance/api/bootstrap").json()
    assert (
        bootstrap["csrf_token_authority"] == "ANTI_CSRF_ONLY_NOT_AUTHENTICATED_IDENTITY"
    )
    for route in (
        "/verification",
        "/diagnostic-inbox",
        "/diagnostic-detail",
        "/create-resolution-proposal",
        "/proposal-review",
        "/approved-amendment-requests",
        "/governance-audit-trail",
    ):
        assert http.get(route).status_code == 200
    assert http.get("/", headers={"Host": "evil.example"}).status_code == 403


@pytest.mark.parametrize(
    ("kwargs", "status", "code"),
    [
        (
            {
                "headers": {
                    "Origin": "http://testserver",
                    "Content-Type": "application/json",
                }
            },
            403,
            "CSRF_REJECTED",
        ),
        (
            {
                "headers": {
                    "Origin": "https://evil.example",
                    "X-CSRF-Token": "test-csrf-token",
                    "Content-Type": "application/json",
                }
            },
            403,
            "ORIGIN_REJECTED",
        ),
        (
            {
                "headers": {
                    "Origin": "http://testserver",
                    "X-CSRF-Token": "test-csrf-token",
                    "Content-Type": "text/plain",
                },
                "content": b"{}",
            },
            400,
            "CONTENT_TYPE_REJECTED",
        ),
    ],
)
def test_write_security_rejects_csrf_origin_and_content_type(
    tmp_path: Path, kwargs, status: int, code: str
) -> None:
    http, _ = client(tmp_path)
    response = http.post("/governance/api/proposals", json=request_body(), **kwargs)
    assert response.status_code == status
    assert response.json()["code"] == code


def test_oversized_body_and_forbidden_methods_are_blocked(tmp_path: Path) -> None:
    http, _ = client(tmp_path)
    response = http.post(
        "/governance/api/proposals",
        headers=headers(),
        content=b"{" + b"x" * MAX_BODY_BYTES + b"}",
    )
    assert response.status_code == 413
    assert response.json()["code"] == "BODY_TOO_LARGE"
    for method in ("put", "patch", "delete"):
        response = getattr(http, method)("/governance/api/workspace")
        assert response.status_code == 405
    assert http.request("CONNECT", "/governance/api/workspace").status_code == 405


def test_duplicate_json_keys_fail_closed(tmp_path: Path) -> None:
    http, _ = client(tmp_path)
    response = http.post(
        "/governance/api/proposals",
        headers=headers(),
        content=b'{"expected_workspace_revision":0,"expected_workspace_revision":1}',
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"


@pytest.mark.parametrize(
    "field", ["workspace_path", "authority_package_path", "artifact_path", "file_path"]
)
def test_http_body_cannot_control_paths(tmp_path: Path, field: str) -> None:
    http, _ = client(tmp_path)
    body = request_body()
    body[field] = "../../escape"
    response = http.post("/governance/api/proposals", headers=headers(), json=body)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"


def test_workspace_path_is_frozen_at_startup(tmp_path: Path) -> None:
    with pytest.raises(GovernanceError):
        GovernanceWorkspaceStore(tmp_path / ".." / "escape.json", authority)


def test_valid_http_create_submit_review_and_replay(tmp_path: Path) -> None:
    http, _ = client(tmp_path)
    created = http.post(
        "/governance/api/proposals", headers=headers(), json=request_body()
    )
    assert created.status_code == 201
    proposal = created.json()
    digest = proposal["proposal_id"].rsplit(":", 1)[-1]
    submitted = http.post(
        f"/governance/api/proposals/{digest}/submit",
        headers=headers(),
        json={
            "expected_workspace_revision": 1,
            "expected_head_hash": http.get("/governance/api/bootstrap").json()[
                "head_event_hash"
            ],
        },
    )
    assert submitted.status_code == 200 and submitted.json()["status"] == "SUBMITTED"
    replay = http.post(
        f"/governance/api/proposals/{digest}/submit",
        headers=headers(),
        json={
            "expected_workspace_revision": 2,
            "expected_head_hash": http.get("/governance/api/bootstrap").json()[
                "head_event_hash"
            ],
        },
    )
    assert replay.status_code == 409 and replay.json()["code"] == "REPLAY_DETECTED"
    reviewed = http.post(
        f"/governance/api/proposals/{digest}/review",
        headers=headers(),
        json={
            "expected_workspace_revision": 2,
            "expected_head_hash": http.get("/governance/api/bootstrap").json()[
                "head_event_hash"
            ],
            "decision": "APPROVE_FOR_AMENDMENT",
            "review_note": "Explicit human approval for future amendment only",
            "reviewed_by_label": "operator reviewer label",
            "explicit_human_action": True,
        },
    )
    assert reviewed.status_code == 200
    assert (
        reviewed.json()["amendment_request"]["status"]
        == "APPROVED_FOR_FUTURE_MODELING_AMENDMENT"
    )


def test_xss_is_text_only_and_no_external_browser_capabilities() -> None:
    root = Path("web/governance")
    javascript = (root / "assets/app.js").read_text(encoding="utf-8")
    html = (root / "index.html").read_text(encoding="utf-8")
    forbidden = (
        "innerHTML",
        "dangerouslySetInnerHTML",
        "eval(",
        "new Function",
        "document.write",
        "serviceWorker",
    )
    assert all(marker not in javascript and marker not in html for marker in forbidden)
    assert "textContent" in javascript and "https://" not in html
    assert "This approval does not modify the authoritative ontology" in html
    forbidden_labels = (
        "KG Updated",
        "Fact Confirmed",
        "Conflict Resolved",
        "Data Corrected",
    )
    assert all(label not in html for label in forbidden_labels)
