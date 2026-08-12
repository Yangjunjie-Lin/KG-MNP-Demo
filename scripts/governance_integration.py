#!/usr/bin/env python3
"""Licensed Application Phase04 closure with executed governance/security probes."""

from __future__ import annotations

import copy
import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

import httpx
import uvicorn
from fastapi.testclient import TestClient

import application_integration as phase01_harness
from kg_mnp_demo.application.publication_binding import PublicationBinding
from kg_mnp_demo.application.query_registry import QueryRegistry
from kg_mnp_demo.application.readonly_client import ReadOnlyGraphDBClient
from kg_mnp_demo.application.service import ApplicationService
from kg_mnp_demo.diagnostics.attestation import build_application_phase03_attestation
from kg_mnp_demo.diagnostics.authority_loader import load_verified_authority_snapshot
from kg_mnp_demo.diagnostics.engine import reconstruct_diagnostics
from kg_mnp_demo.governance.artifact_verifier import verify_application_phase04_artifact
from kg_mnp_demo.governance.attestation import build_application_phase04_attestation
from kg_mnp_demo.governance.authority_binding import (
    GovernanceAuthority,
    load_verified_phase03_authority,
)
from kg_mnp_demo.governance.contracts import strict_json_file
from kg_mnp_demo.governance.errors import GovernanceError
from kg_mnp_demo.governance.event_log import event_identity_content
from kg_mnp_demo.governance.proposal import empty_payload
from kg_mnp_demo.governance.runtime import create_governance_app
from kg_mnp_demo.governance.state_machine import require_transition
from kg_mnp_demo.governance.validator import (
    validate_governance_workspace_against_authorities,
    workspace_semantic_content,
)
from kg_mnp_demo.governance.workspace import (
    GovernanceWorkspace,
    GovernanceWorkspaceStore,
)
from kg_mnp_demo.graphdb.client import GraphDBClient
from kg_mnp_demo.graphdb.importer import import_package
from kg_mnp_demo.graphdb.policy import load_graphdb_policy
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def _controlled_snapshot(bindings) -> dict[str, Any]:
    publication = bindings.publication_id

    def requirement(name: str, *, maximum: int | None = 1):
        focus = f"urn:kg-mnp:phase04:{name}"
        if name == "missing":
            focus += ":<img src=x onerror=window.__xss=1>"
        return {
            "focus_node": focus,
            "path": "urn:kg-mnp:phase04:controlled-property",
            "requirement_type": "CONTROLLED_SHACL_MIN_MAX_COUNT",
            "authority_iri": f"urn:kg-mnp:phase04:constraint:{name}",
            "shape_iri": f"urn:kg-mnp:phase04:shape:{name}",
            "constraint_iri": f"urn:kg-mnp:phase04:constraint:{name}",
            "module": "phase04-controlled-scenario",
            "publication_id": publication,
            "min_count": 1,
            "max_count": maximum,
        }

    conflict_focus = "urn:kg-mnp:phase04:conflict"
    predicate = "urn:kg-mnp:phase04:controlled-property"
    rejected_focus = "urn:kg-mnp:phase04:rejected"
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
            },
            {
                "subject": conflict_focus,
                "predicate": predicate,
                "object": "confirmed-b",
            },
        ],
        "constraint_results": [],
        "candidates": [
            {
                "focus_node": rejected_focus,
                "path": predicate,
                "value": "rejected-value",
                "outcome": "REJECT",
                "candidate_ref": "urn:kg-mnp:phase04:candidate:rejected",
                "review_decision_ref": "urn:kg-mnp:phase04:decision:rejected",
                "evidence_refs": [],
                "source_refs": [],
            }
        ],
        "conflict_rules": [],
    }


def _controlled_phase03_authority(
    snapshot, source_attestation: dict[str, Any], output: Path
):
    controlled = _controlled_snapshot(snapshot.authority_bindings)
    package = reconstruct_diagnostics(controlled)
    repeated = reconstruct_diagnostics(controlled)
    if package.canonical_bytes() != repeated.canonical_bytes():
        raise RuntimeError("controlled Phase03 reconstruction is not deterministic")
    attacked = copy.deepcopy(controlled)
    attacked["requirements"].reverse()
    if package.canonical_bytes() != reconstruct_diagnostics(attacked).canonical_bytes():
        raise RuntimeError("controlled Phase03 permutation changed diagnostics")
    attestation = build_application_phase03_attestation(
        commit_sha=source_attestation["commit_sha"],
        authority_bindings=snapshot.authority_bindings,
        package=package,
        repository_before_hash=source_attestation["repository_before_hash"],
        repository_after_hash=source_attestation["repository_after_hash"],
        controlled_scenarios_total=source_attestation["controlled_scenarios_total"],
        controlled_scenarios_passed=source_attestation["controlled_scenarios_passed"],
        determinism_runs=max(2, source_attestation["determinism_runs"]),
        determinism_passed=True,
        permutation_attacks=max(1, source_attestation["permutation_attacks"]),
        permutation_passed=True,
        authority_tamper_attempts=source_attestation["authority_tamper_attempts"],
        authority_tamper_blocked=source_attestation["authority_tamper_blocked"],
        missingness_attacks=source_attestation["missingness_attacks"],
        missingness_expected_results=source_attestation["missingness_expected_results"],
        conflict_attacks=source_attestation["conflict_attacks"],
        conflict_expected_results=source_attestation["conflict_expected_results"],
        evidence_attacks=source_attestation["evidence_attacks"],
        evidence_expected_results=source_attestation["evidence_expected_results"],
        xss_attempts=source_attestation["xss_attempts"],
        xss_blocked=source_attestation["xss_blocked"],
        external_requests=source_attestation["external_requests"],
        direct_graphdb_attempts=source_attestation["direct_graphdb_attempts"],
        direct_graphdb_blocked=source_attestation["direct_graphdb_blocked"],
    )
    package_path = output / "deterministic-diagnostic-package.json"
    attestation_path = output / "application-phase03-attestation.json"
    snapshot_path = output / "authority-snapshot.json"
    _write(package_path, package.to_dict())
    _write(attestation_path, attestation)
    _write(snapshot_path, controlled)
    authority = load_verified_phase03_authority(
        diagnostic_package=package_path,
        phase03_attestation=attestation_path,
        authority_snapshot=controlled,
    )
    return authority, package_path, attestation_path, snapshot_path


def _payload(value: str = "proposed-value") -> dict[str, Any]:
    result = empty_payload()
    result["rdf_term"] = {
        "term_type": "LITERAL",
        "iri": None,
        "lexical_form": value,
        "datatype_iri": "http://www.w3.org/2001/XMLSchema#string",
        "language": None,
    }
    return result


def _proposal_args(
    issue: dict[str, Any],
    *,
    value: str = "proposed-value",
    proposal_type: str = "PROPOSE_VALUE_CANDIDATE",
):
    payload = _payload(value)
    if proposal_type == "REQUEST_REVIEW_REOPEN":
        payload = empty_payload()
        payload["review_reopen_reason"] = value
    return {
        "target_diagnostic_id": issue["diagnostic_id"],
        "target_diagnostic_basis_hash": issue["diagnostic_basis_hash"],
        "proposal_type": proposal_type,
        "proposed_payload": payload,
        "rationale": "Operator-entered rationale. This proposal is not a fact.",
        "created_by_label": "operator-supplied label",
        "proposal_revision": 1,
    }


def _record(
    probes: list[dict[str, Any]],
    category: str,
    attack: str,
    expected: str,
    action: Callable[[], str],
):
    try:
        actual = action()
    except GovernanceError as exc:
        actual = exc.code.value
    except Exception as exc:
        actual = type(exc).__name__
    passed = actual == expected
    probe = {
        "probe_id": "urn:kg-mnp:phase04-probe:"
        + semantic_hash({"category": category, "attack": attack, "expected": expected}),
        "category": category,
        "attack": attack,
        "expected_outcome": expected,
        "actual_outcome": actual,
        "blocked": passed,
        "status": "PASS" if passed else "FAILED",
    }
    probes.append(probe)
    if not passed:
        raise RuntimeError(f"probe failed: {attack}: expected {expected}, got {actual}")


def _expect_validation(workspace, authority, *, anchor=None) -> str:
    validate_governance_workspace_against_authorities(
        workspace, authority, expected_workspace_hash=anchor
    )
    return "ACCEPTED"


def _rehash_workspace(value: dict[str, Any]) -> None:
    previous = "GENESIS"
    for sequence, event in enumerate(value["events"], start=1):
        event["sequence"] = sequence
        event["previous_event_hash"] = previous
        event["payload_hash"] = semantic_hash(event["payload"])
        event["event_id"] = semantic_hash(event_identity_content(event))
        previous = event["event_id"]
    value["workspace_revision"] = len(value["events"])
    value["head_event_hash"] = previous
    value["workspace_hash"] = semantic_hash(workspace_semantic_content(value))


def _run_governance(authority: GovernanceAuthority, output: Path):
    current = [authority]
    store = GovernanceWorkspaceStore(
        output / "governance-workspace.json", lambda: current[0]
    )
    workspace = store.initialize(authority)
    issues = list(authority.issues.values())
    missing = next(
        i
        for i in issues
        if i["classification"] == "REQUIRED_VALUE_MISSING"
        and ":missing:" in i["focus_node"]
    )
    rejected = next(
        i for i in issues if i["classification"] == "REJECTED_CANDIDATE_HISTORY"
    )
    conflict = next(
        i for i in issues if i["classification"] == "CONFIRMED_VALUE_CONFLICT"
    )

    def lifecycle(
        issue,
        decision,
        *,
        value="proposed-value",
        proposal_type="PROPOSE_VALUE_CANDIDATE",
    ):
        proposal = workspace.create_proposal(
            expected_workspace_revision=workspace.value["workspace_revision"],
            expected_head_hash=workspace.value["head_event_hash"],
            **_proposal_args(issue, value=value, proposal_type=proposal_type),
        )
        workspace.submit_proposal(
            proposal["proposal_id"],
            expected_workspace_revision=workspace.value["workspace_revision"],
            expected_head_hash=workspace.value["head_event_hash"],
        )
        result = workspace.review_proposal(
            proposal["proposal_id"],
            decision=decision,
            review_note="Explicit human review for future amendment processing only.",
            reviewed_by_label="operator-supplied reviewer label",
            explicit_human_action=True,
            expected_workspace_revision=workspace.value["workspace_revision"],
            expected_head_hash=workspace.value["head_event_hash"],
        )
        return proposal, result

    missing_proposal, _ = lifecycle(missing, "APPROVE_FOR_AMENDMENT")
    rejected_proposal, _ = lifecycle(
        rejected,
        "APPROVE_FOR_AMENDMENT",
        value="Reopen the rejected candidate as a new proposal lineage",
        proposal_type="REQUEST_REVIEW_REOPEN",
    )
    conflict_proposal, _ = lifecycle(conflict, "APPROVE_FOR_AMENDMENT")
    _, rejected_result = lifecycle(missing, "REJECT", value="rejected-review-value")
    _, deferred_result = lifecycle(missing, "DEFER", value="deferred-review-value")
    if (
        rejected_result["amendment_request"] is not None
        or deferred_result["amendment_request"] is not None
    ):
        raise RuntimeError("reject/defer generated amendment request")
    if rejected_proposal["proposal_id"] in rejected.get(
        "candidate_refs", []
    ) or not rejected.get("review_decision_refs"):
        raise RuntimeError("rejected candidate history was overwritten")
    if (
        authority.require_issue(conflict["diagnostic_id"])["classification"]
        != "CONFIRMED_VALUE_CONFLICT"
    ):
        raise RuntimeError("conflict disappeared after governance approval")
    if (
        authority.require_issue(missing["diagnostic_id"])["classification"]
        != "REQUIRED_VALUE_MISSING"
    ):
        raise RuntimeError(
            "missingness diagnostic disappeared after governance approval"
        )
    if missing_proposal["proposal_id"] == conflict_proposal["proposal_id"]:
        raise RuntimeError("proposal lineage collision")

    probes: list[dict[str, Any]] = []
    for current_state, target in (
        ("DRAFT", "APPROVED_FOR_AMENDMENT"),
        ("REJECTED", "APPROVED_FOR_AMENDMENT"),
        ("APPROVED_FOR_AMENDMENT", "DRAFT"),
        ("DEFERRED", "APPROVED_FOR_AMENDMENT"),
    ):
        _record(
            probes,
            "ILLEGAL_TRANSITION",
            f"{current_state}->{target}",
            "ILLEGAL_STATE_TRANSITION"
            if current_state == "DRAFT"
            else "TERMINAL_STATE_IMMUTABLE",
            lambda c=current_state, t=target: (require_transition(c, t), "ACCEPTED")[1],
        )

    replay_workspace = GovernanceWorkspace.initialize(authority)
    replay_proposal = replay_workspace.create_proposal(
        expected_workspace_revision=0, **_proposal_args(missing)
    )
    replay_workspace.submit_proposal(
        replay_proposal["proposal_id"], expected_workspace_revision=1
    )
    _record(
        probes,
        "REPLAY",
        "duplicate submit request",
        "REPLAY_DETECTED",
        lambda: (
            replay_workspace.submit_proposal(
                replay_proposal["proposal_id"], expected_workspace_revision=2
            ),
            "ACCEPTED",
        )[1],
    )
    approved_proposal = next(
        proposal
        for proposal in workspace.reconstruct()["proposals"]
        if proposal["status"] == "APPROVED_FOR_AMENDMENT"
    )
    _record(
        probes,
        "REPLAY",
        "duplicate approval request",
        "REPLAY_DETECTED",
        lambda: (
            workspace.review_proposal(
                approved_proposal["proposal_id"],
                decision="APPROVE_FOR_AMENDMENT",
                review_note="duplicate approval",
                reviewed_by_label="label",
                explicit_human_action=True,
                expected_workspace_revision=workspace.value["workspace_revision"],
                expected_head_hash=workspace.value["head_event_hash"],
            ),
            "ACCEPTED",
        )[1],
    )
    _record(
        probes,
        "CONCURRENCY",
        "old expected workspace revision",
        "CONCURRENCY_CONFLICT",
        lambda: (
            replay_workspace.review_proposal(
                replay_proposal["proposal_id"],
                decision="REJECT",
                review_note="old revision",
                reviewed_by_label="label",
                explicit_human_action=True,
                expected_workspace_revision=1,
            ),
            "ACCEPTED",
        )[1],
    )

    stale = GovernanceAuthority(
        **{
            **authority.binding,
            "diagnostic_package_hash": "0" * 64,
            "issues": authority.issues,
        }
    )
    stale_current = [authority]
    stale_workspace = GovernanceWorkspace.initialize(
        authority, lambda: stale_current[0]
    )
    stale_current[0] = stale
    _record(
        probes,
        "STALE_BINDING",
        "create after Phase03 package changed",
        "STALE_DIAGNOSTIC_BINDING",
        lambda: (
            stale_workspace.create_proposal(
                expected_workspace_revision=0,
                **_proposal_args(missing),
            ),
            "ACCEPTED",
        )[1],
    )
    stale_current[0] = authority
    stale_proposal = stale_workspace.create_proposal(
        expected_workspace_revision=0, **_proposal_args(missing)
    )
    stale_current[0] = stale
    _record(
        probes,
        "STALE_BINDING",
        "submit after Phase03 package changed",
        "STALE_DIAGNOSTIC_BINDING",
        lambda: (
            stale_workspace.submit_proposal(
                stale_proposal["proposal_id"], expected_workspace_revision=1
            ),
            "ACCEPTED",
        )[1],
    )
    _record(
        probes,
        "STALE_BINDING",
        "review after Phase03 package changed",
        "STALE_DIAGNOSTIC_BINDING",
        lambda: (
            stale_workspace.review_proposal(
                stale_proposal["proposal_id"],
                decision="REJECT",
                review_note="stale",
                reviewed_by_label="label",
                explicit_human_action=True,
                expected_workspace_revision=1,
            ),
            "ACCEPTED",
        )[1],
    )
    _record(
        probes,
        "STALE_BINDING",
        "approve after Phase03 package changed",
        "STALE_DIAGNOSTIC_BINDING",
        lambda: (
            stale_workspace.review_proposal(
                stale_proposal["proposal_id"],
                decision="APPROVE_FOR_AMENDMENT",
                review_note="stale",
                reviewed_by_label="label",
                explicit_human_action=True,
                expected_workspace_revision=1,
            ),
            "ACCEPTED",
        )[1],
    )

    unknown = _proposal_args(missing)
    unknown["target_diagnostic_id"] = "urn:kg-mnp:diagnostic:" + "1" * 64
    _record(
        probes,
        "AUTHORITY",
        "unknown diagnostic ID",
        "UNKNOWN_DIAGNOSTIC",
        lambda: (
            replay_workspace.create_proposal(expected_workspace_revision=2, **unknown),
            "ACCEPTED",
        )[1],
    )

    wrong_publication = copy.deepcopy(workspace.value)
    wrong_publication["events"][0]["payload"]["publication_id"] = (
        "urn:kg-mnp:e2e-publication:" + "9" * 64
    )
    _rehash_workspace(wrong_publication)
    _record(
        probes,
        "AUTHORITY",
        "wrong publication identity",
        "WORKSPACE_TAMPERED",
        lambda: (
            _expect_validation(
                wrong_publication,
                authority,
                anchor=workspace.value["workspace_hash"],
            ),
            "ACCEPTED",
        )[1],
    )
    wrong_hash = _proposal_args(missing)
    wrong_hash["target_diagnostic_basis_hash"] = "2" * 64
    _record(
        probes,
        "AUTHORITY",
        "wrong diagnostic basis hash",
        "STALE_DIAGNOSTIC_BINDING",
        lambda: (
            replay_workspace.create_proposal(
                expected_workspace_revision=2, **wrong_hash
            ),
            "ACCEPTED",
        )[1],
    )

    final_value = workspace.value
    anchor = final_value["workspace_hash"]
    attacks = {}
    for name in (
        "proposal",
        "review",
        "delete",
        "insert",
        "reorder",
        "self-consistent-rehash",
        "target-diagnostic-rehash",
    ):
        attacked = copy.deepcopy(final_value)
        if name == "proposal":
            attacked["events"][0]["payload"]["rationale"] = "tampered proposal"
        elif name == "review":
            attacked["events"][2]["payload"]["review_note"] = "tampered review"
        elif name == "delete":
            del attacked["events"][1]
        elif name == "insert":
            attacked["events"].insert(1, copy.deepcopy(attacked["events"][0]))
        elif name == "reorder":
            attacked["events"][0], attacked["events"][1] = (
                attacked["events"][1],
                attacked["events"][0],
            )
        elif name == "self-consistent-rehash":
            attacked["events"][2]["payload"]["review_note"] = "changed and rehashed"
            _rehash_workspace(attacked)
        else:
            attacked["events"][0]["payload"]["target_diagnostic_id"] = conflict[
                "diagnostic_id"
            ]
            attacked["events"][0]["payload"]["target_diagnostic_basis_hash"] = conflict[
                "diagnostic_basis_hash"
            ]
            _rehash_workspace(attacked)
        attacks[name] = attacked
        _record(
            probes,
            "TAMPER",
            name,
            "WORKSPACE_TAMPERED",
            lambda a=attacked: (
                _expect_validation(a, authority, anchor=anchor),
                "ACCEPTED",
            )[1],
        )
    return store, workspace, probes, attacks


def _http_and_browser_probes(
    store: GovernanceWorkspaceStore, probes: list[dict[str, Any]]
):
    token = "phase04-integration-csrf"
    app = create_governance_app(store, csrf_value=token)
    with TestClient(app, raise_server_exceptions=False) as http:

        def outcome(response):
            return str(response.json().get("code", response.status_code))

        _record(
            probes,
            "CSRF",
            "missing CSRF token",
            "CSRF_REJECTED",
            lambda: outcome(
                http.post(
                    "/governance/api/proposals",
                    headers={
                        "Origin": "http://testserver",
                        "Content-Type": "application/json",
                    },
                    json={},
                )
            ),
        )
        _record(
            probes,
            "CSRF",
            "cross-origin POST",
            "ORIGIN_REJECTED",
            lambda: outcome(
                http.post(
                    "/governance/api/proposals",
                    headers={
                        "Origin": "https://evil.example",
                        "X-CSRF-Token": token,
                        "Content-Type": "application/json",
                    },
                    json={},
                )
            ),
        )
        _record(
            probes,
            "HTTP",
            "oversized body",
            "BODY_TOO_LARGE",
            lambda: outcome(
                http.post(
                    "/governance/api/proposals",
                    headers={
                        "Origin": "http://testserver",
                        "X-CSRF-Token": token,
                        "Content-Type": "application/json",
                    },
                    content=b"x" * (65536 + 1),
                )
            ),
        )
        _record(
            probes,
            "HTTP",
            "unexpected Content-Type",
            "CONTENT_TYPE_REJECTED",
            lambda: outcome(
                http.post(
                    "/governance/api/proposals",
                    headers={
                        "Origin": "http://testserver",
                        "X-CSRF-Token": token,
                        "Content-Type": "text/plain",
                    },
                    content=b"{}",
                )
            ),
        )
        _record(
            probes,
            "DIRECT_GRAPHDB",
            "GraphDB URL injection",
            "INVALID_REQUEST",
            lambda: outcome(
                http.post(
                    "/repositories/kg-mnp/statements",
                    headers={
                        "Origin": "http://testserver",
                        "X-CSRF-Token": token,
                        "Content-Type": "application/json",
                    },
                    json={"url": "http://127.0.0.1:7200"},
                )
            ),
        )
        body = {
            "expected_workspace_revision": store.load().value["workspace_revision"],
            "expected_head_hash": store.load().value["head_event_hash"],
            **_proposal_args(
                next(iter(store.current_authority().issues.values())),
                value="INSERT DATA { <s> <p> <o> }",
            ),
        }
        _record(
            probes,
            "RDF_MUTATION",
            "raw RDF/SPARQL patch",
            "INVALID_REQUEST",
            lambda: outcome(
                http.post(
                    "/governance/api/proposals",
                    headers={
                        "Origin": "http://testserver",
                        "X-CSRF-Token": token,
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
            ),
        )
        raw_rdf = copy.deepcopy(body)
        raw_rdf["raw_rdf_patch"] = "<urn:s> <urn:p> <urn:o> ."
        _record(
            probes,
            "RDF_MUTATION",
            "arbitrary raw RDF patch field",
            "INVALID_REQUEST",
            lambda: outcome(
                http.post(
                    "/governance/api/proposals",
                    headers={
                        "Origin": "http://testserver",
                        "X-CSRF-Token": token,
                        "Content-Type": "application/json",
                    },
                    json=raw_rdf,
                )
            ),
        )
        traversal = copy.deepcopy(body)
        traversal["workspace_path"] = "..%252f..%252fescape"
        _record(
            probes,
            "INPUT",
            "path traversal and double encoding",
            "INVALID_REQUEST",
            lambda: outcome(
                http.post(
                    "/governance/api/proposals",
                    headers={
                        "Origin": "http://testserver",
                        "X-CSRF-Token": token,
                        "Content-Type": "application/json",
                    },
                    json=traversal,
                )
            ),
        )

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="error", access_log=False
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(200):
        try:
            if (
                httpx.get(
                    base + "/governance/api/status", timeout=0.2, trust_env=False
                ).status_code
                == 200
            ):
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    external: list[str] = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()

            def route(value):
                if value.request.url.startswith(base):
                    value.continue_()
                else:
                    external.append(value.request.url)
                    value.abort()

            page.route("**/*", route)
            page.goto(base, wait_until="networkidle")
            page.locator("button[data-view='inbox']").click()
            page.locator(
                "#diagnostic-list button",
                has_text="REQUIRED_VALUE_MISSING",
            ).first.click()
            xss = page.evaluate(
                "window.__xss === undefined && document.querySelectorAll('#diagnostic-detail img').length === 0"
            )
            workers = page.evaluate(
                "navigator.serviceWorker ? navigator.serviceWorker.getRegistrations().then(x => x.length) : 0"
            )
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    _record(
        probes,
        "XSS",
        "malicious diagnostic rendered in browser",
        "XSS_BLOCKED",
        lambda: "XSS_BLOCKED" if xss and not external else "XSS_EXECUTED",
    )
    return len(external), int(workers)


def main() -> int:
    publication_package = ROOT / "runtime_outputs/publication/full-confirmation"
    manifest = strict_json_file(publication_package / "publication-manifest.json")
    publication_hash = manifest["publication_semantic_hash"]
    publication_attestation = (
        ROOT
        / "runtime_reports/publication"
        / publication_hash
        / "publication-attestation.json"
    )
    phase01 = ROOT / "runtime_reports/application" / publication_hash
    phase02 = ROOT / "runtime_reports/workbench" / publication_hash
    phase03_report = ROOT / "runtime_reports/diagnostics" / publication_hash
    source_phase03_attestation = strict_json_file(
        phase03_report / "application-phase03-attestation.json"
    )
    snapshot = load_verified_authority_snapshot(
        publication_package_directory=publication_package,
        publication_attestation_path=publication_attestation,
        publication_scenario="full-confirmation",
        phase01_artifact_directory=phase01,
        phase02_artifact_directory=phase02,
    )
    controlled_dir = ROOT / "runtime_outputs/governance/controlled-authority"
    authority, package_path, _, _ = _controlled_phase03_authority(
        snapshot, source_phase03_attestation, controlled_dir
    )
    diagnostic_before_bytes = package_path.read_bytes()
    diagnostic_before = authority.diagnostic_package_hash

    binding = PublicationBinding.verify(
        publication_package,
        publication_attestation,
        publication_scenario="full-confirmation",
    )
    graphdb_package = (
        ROOT / "runtime_outputs/graphdb" / manifest["graphdb_publication_semantic_hash"]
    )
    license_path, generated_license = phase01_harness._license()
    graphdb_port = _free_port()
    override = ROOT / "runtime_outputs/governance/.compose-license.yml"
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text(
        "services:\n  graphdb:\n    ports: !override\n"
        f"      - '127.0.0.1:{graphdb_port}:7200'\n"
        "    volumes:\n"
        f"      - '{license_path.as_posix()}:/opt/graphdb/home/conf/graphdb.license:ro'\n",
        encoding="utf-8",
    )
    files = [phase01_harness.COMPOSE, override]
    project = "kgmnp-governance-" + publication_hash[:12]
    base_url = f"http://127.0.0.1:{graphdb_port}"
    setup = GraphDBClient(base_url=base_url, timeout=60.0, retries=0)
    imported = False
    try:
        phase01_harness._compose(project, files, "up", "-d")
        phase01_harness._wait_graphdb(setup)
        setup.verify_runtime_readiness(
            expected_product_version=load_graphdb_policy()["graphdb"]["product_version"]
        )
        import_package(setup, graphdb_package)
        imported = True
        service = ApplicationService(
            binding=binding,
            registry=QueryRegistry.load(),
            client=ReadOnlyGraphDBClient(base_url=base_url, timeout=8.0),
        )
        before_status = service.runtime_check()
        repository_before = before_status["live_graphdb_semantic_hash"]
        workspace_dir = ROOT / "runtime_outputs/governance/workspace"
        store, workspace, probes, _ = _run_governance(authority, workspace_dir)
        external_requests, service_workers = _http_and_browser_probes(store, probes)
        after_status = service.runtime_check()
        repository_after = after_status["live_graphdb_semantic_hash"]
        if package_path.read_bytes() != diagnostic_before_bytes:
            raise RuntimeError("Phase03 controlled diagnostic package bytes changed")
        diagnostic_after = load_verified_phase03_authority(
            diagnostic_package=package_path,
            phase03_attestation=controlled_dir / "application-phase03-attestation.json",
            authority_snapshot=strict_json_file(
                controlled_dir / "authority-snapshot.json"
            ),
        ).diagnostic_package_hash
        commit_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        attestation = build_application_phase04_attestation(
            commit_sha=commit_sha,
            upstream_verification_mode="LOCAL_LICENSED",
            authority=authority,
            workspace=workspace.value,
            probes=probes,
            repository_before_hash=repository_before,
            repository_after_hash=repository_after,
            diagnostic_hash_before=diagnostic_before,
            diagnostic_hash_after=diagnostic_after,
        )
        state = workspace.reconstruct()
        report = ROOT / "runtime_reports/governance" / publication_hash
        documents = {
            "application-phase04-attestation.json": attestation,
            "governance-summary.json": {
                "contract_version": "1.0",
                "workspace": workspace.value,
                "workspace_hash": workspace.value["workspace_hash"],
                "workspace_revision": workspace.value["workspace_revision"],
                "proposals_created": attestation["proposals_created"],
                "proposals_submitted": attestation["proposals_submitted"],
                "reviews_approved": attestation["reviews_approved"],
                "reviews_rejected": attestation["reviews_rejected"],
                "reviews_deferred": attestation["reviews_deferred"],
                "approved_amendment_requests": attestation[
                    "approved_amendment_requests"
                ],
                "status": "PASS",
            },
            "state-machine-summary.json": {
                "contract_version": "1.0",
                "valid_transitions": [
                    "DRAFT->SUBMITTED",
                    "SUBMITTED->APPROVED_FOR_AMENDMENT",
                    "SUBMITTED->REJECTED",
                    "SUBMITTED->DEFERRED",
                ],
                "invalid_transition_probes": [
                    p["probe_id"]
                    for p in probes
                    if p["category"] == "ILLEGAL_TRANSITION"
                ],
                "status": "PASS",
            },
            "authority-binding.json": {
                "contract_version": "1.0",
                **authority.binding,
                "status": "PASS",
            },
            "security-summary.json": {
                "contract_version": "1.0",
                "probes": probes,
                "external_requests": external_requests,
                "service_workers": service_workers,
                "status": "PASS",
            },
        }
        if (
            len(state["approved_amendment_requests"])
            != attestation["approved_amendment_requests"]
        ):
            raise RuntimeError("amendment aggregation mismatch")
        for name, value in documents.items():
            _write(report / name, value)
        verified = verify_application_phase04_artifact(
            report,
            authority=authority,
            expected_commit_sha=commit_sha,
            expected_workspace_hash=workspace.value["workspace_hash"],
        )
        print(
            json.dumps(
                {
                    **verified,
                    "repository_before": repository_before,
                    "repository_after": repository_after,
                    "diagnostic_before": diagnostic_before,
                    "diagnostic_after": diagnostic_after,
                    "probe_count": len(probes),
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        if imported:
            try:
                setup.delete_generated_repository(binding.repository_id)
            except Exception:
                pass
        phase01_harness._compose(
            project, files, "down", "-v", "--remove-orphans", check=False
        )
        override.unlink(missing_ok=True)
        if generated_license is not None:
            generated_license.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
