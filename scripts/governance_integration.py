#!/usr/bin/env python3
"""Licensed Application Phase04 closure with executed governance/security probes."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import application_integration as phase01_harness
import httpx
import uvicorn
from fastapi.testclient import TestClient
from governance_controlled_fixture import (
    ControlledDiagnosticFixture,
    controlled_governance_app_for_test_harness,
    controlled_governance_authority_for_test_harness,
    controlled_governance_store_for_test_harness,
    controlled_governance_workspace_for_test_harness,
)

from kg_mnp_demo.application.publication_binding import PublicationBinding
from kg_mnp_demo.application.query_registry import QueryRegistry
from kg_mnp_demo.application.readonly_client import ReadOnlyGraphDBClient
from kg_mnp_demo.application.service import ApplicationService
from kg_mnp_demo.diagnostics.artifact_verifier import (
    verify_application_phase03_artifact,
)
from kg_mnp_demo.diagnostics.authority_binding import AuthorityBindings
from kg_mnp_demo.diagnostics.engine import reconstruct_diagnostics
from kg_mnp_demo.governance.artifact_verifier import verify_application_phase04_artifact
from kg_mnp_demo.governance.attestation import build_application_phase04_attestation
from kg_mnp_demo.governance.authority_binding import (
    GovernanceAuthority,
    load_production_phase03_authority,
)
from kg_mnp_demo.governance.contracts import strict_json_file
from kg_mnp_demo.governance.errors import GovernanceError
from kg_mnp_demo.governance.event_log import event_identity_content
from kg_mnp_demo.governance.proposal import empty_payload
from kg_mnp_demo.governance.state_machine import require_transition
from kg_mnp_demo.governance.validator import (
    validate_governance_workspace_against_authorities,
    workspace_semantic_content,
)
from kg_mnp_demo.governance.workspace import (
    GovernanceWorkspace,
    GovernanceWorkspaceStore,
)
from kg_mnp_demo.graphdb.client import GraphDBClient, GraphDBClientError
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
    passed = actual == expected
    probe = {
        "probe_id": "urn:kg-mnp:test-fixture:phase04:probe:"
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


def _verify_laundering_attacks(
    *,
    production_authority: GovernanceAuthority,
    fixture: ControlledDiagnosticFixture,
    publication_package: Path,
    publication_attestation: Path,
    phase01: Path,
    phase02: Path,
    phase03: Path,
    expected_commit_sha: str,
    probes: list[dict[str, Any]],
) -> None:
    """Execute the laundering matrix against the closed production loader."""

    def fixture_substitution() -> str:
        try:
            load_production_phase03_authority(
                publication_package_directory=publication_package,
                publication_attestation_path=publication_attestation,
                phase01_artifact_directory=phase01,
                phase02_artifact_directory=phase02,
                phase03_artifact_directory=fixture,
                expected_commit_sha=expected_commit_sha,
            )
        except GovernanceError as exc:
            return exc.code.value
        return "ACCEPTED"

    _record(
        probes,
        "AUTHORITY_LAUNDERING",
        "fixture_to_production_substitution",
        "TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY",
        fixture_substitution,
    )

    binding_document = strict_json_file(phase03 / "authority-binding.json")
    bindings = AuthorityBindings.from_dict(
        {
            key: value
            for key, value in binding_document.items()
            if key not in {"contract_version", "status"}
        }
    )
    if (
        bindings.publication_id != production_authority.publication_id
        or bindings.publication_semantic_hash
        != production_authority.publication_semantic_hash
        or bindings.repository_semantic_hash
        != production_authority.repository_semantic_hash
    ):
        raise RuntimeError("Phase03 attack source is not the production authority")

    attacks = (
        "self_minted_phase03_attestation",
        "synthetic_requirement_snapshot",
        "synthetic_fact_snapshot",
        "copied_publication_identity",
        "copied_repository_hash",
        "self_consistent_full_rehash",
    )
    with tempfile.TemporaryDirectory(
        prefix="kg-mnp-phase04-laundering-"
    ) as temporary:
        for attack in attacks:
            snapshot = _laundering_snapshot(
                attack=attack,
                bindings=bindings,
                fixture=fixture,
            )
            package = reconstruct_diagnostics(snapshot).to_dict()
            synthetic_hash = package["manifest"]["package_semantic_hash"]
            if (
                synthetic_hash
                == production_authority.upstream_phase03_diagnostic_package_hash
                or package["authority_bindings"] != bindings.to_dict()
            ):
                raise RuntimeError("synthetic Phase03 package was not a replacement")

            attacked_root = Path(temporary) / attack
            _write_self_minted_phase03_artifact(
                source=phase03,
                destination=attacked_root,
                package=package,
                expected_commit_sha=expected_commit_sha,
            )
            verified = verify_application_phase03_artifact(
                attacked_root,
                expected_commit_sha=expected_commit_sha,
            )
            if (
                verified["status"] != "APPLICATION_DIAGNOSTICS_VERIFIED"
                or verified["diagnostic_package_hash"] != synthetic_hash
            ):
                raise RuntimeError(
                    "self-minted Phase03 artifact was not independently verified"
                )

            def rejected(value=attacked_root) -> str:
                try:
                    load_production_phase03_authority(
                        publication_package_directory=publication_package,
                        publication_attestation_path=publication_attestation,
                        phase01_artifact_directory=phase01,
                        phase02_artifact_directory=phase02,
                        phase03_artifact_directory=value,
                        expected_commit_sha=expected_commit_sha,
                    )
                except GovernanceError as exc:
                    return exc.code.value
                return "ACCEPTED"

            _record(
                probes,
                "AUTHORITY_LAUNDERING",
                attack,
                "AUTHORITY_MISMATCH",
                rejected,
            )

    if production_authority.authority_type != "PRODUCTION_EXACT_PHASE03":
        raise RuntimeError("production authority type was not exact Phase03")


def _laundering_snapshot(
    *,
    attack: str,
    bindings: AuthorityBindings,
    fixture: ControlledDiagnosticFixture,
) -> dict[str, Any]:
    """Construct attacker-authored inputs carrying copied production bindings."""

    namespace = f"urn:kg-mnp:test-fixture:phase04:laundering:{attack}:"
    if attack == "self_consistent_full_rehash":
        snapshot = fixture.authority_snapshot
        snapshot["authority_bindings"] = bindings.to_dict()
        for collection in ("requirements", "conflict_rules"):
            for row in snapshot[collection]:
                row["publication_id"] = bindings.publication_id
        return snapshot

    requirement = {
        "focus_node": namespace + "requirement-focus",
        "path": namespace + "property",
        "requirement_type": "ATTACKER_SYNTHETIC_MIN_COUNT",
        "authority_iri": namespace + "constraint",
        "shape_iri": namespace + "shape",
        "constraint_iri": namespace + "constraint",
        "module": "phase04-authority-laundering-attack",
        "publication_id": bindings.publication_id,
        "min_count": 1,
        "max_count": 1,
    }
    fact = {
        "subject": namespace + "fact-focus",
        "predicate": namespace + "property",
        "object": "attacker-authored-value",
        "assertion_ref": namespace + "assertion",
    }
    candidate = {
        "focus_node": namespace + "candidate-focus",
        "path": namespace + "property",
        "value": "attacker-authored-candidate",
        "outcome": "REJECT",
        "candidate_ref": namespace + "candidate",
        "review_decision_ref": namespace + "decision",
        "evidence_refs": [],
        "source_refs": [],
    }
    snapshot = {
        "authority_bindings": bindings.to_dict(),
        "requirements": [],
        "facts": [],
        "constraint_results": [],
        "candidates": [],
        "conflict_rules": [],
    }
    if attack == "synthetic_fact_snapshot":
        snapshot["facts"] = [fact]
    elif attack == "copied_repository_hash":
        snapshot["facts"] = [fact]
        snapshot["candidates"] = [candidate]
    else:
        snapshot["requirements"] = [requirement]
        if attack == "self_minted_phase03_attestation":
            snapshot["candidates"] = [candidate]
    return snapshot


def _write_self_minted_phase03_artifact(
    *,
    source: Path,
    destination: Path,
    package: dict[str, Any],
    expected_commit_sha: str,
) -> None:
    """Rehash a five-file Phase03 replacement exactly as an attacker would."""

    shutil.copytree(source, destination)
    attestation_path = destination / "application-phase03-attestation.json"
    summary_path = destination / "diagnostics-summary.json"
    determinism_path = destination / "diagnostic-determinism.json"
    attestation = strict_json_file(attestation_path)
    summary = strict_json_file(summary_path)
    determinism = strict_json_file(determinism_path)
    package_hash = package["manifest"]["package_semantic_hash"]
    package_summary = package["summary"]
    package_coverage = package["coverage"]
    attestation.update(
        {
            "commit_sha": expected_commit_sha,
            "diagnostic_package_hash": package_hash,
            "issues_total": package_summary["issues_total"],
            "issues_by_classification": package_summary[
                "issues_by_classification"
            ],
            "requirements_evaluated": package_coverage[
                "requirements_evaluated"
            ],
            "constraints_evaluated": package_coverage[
                "shacl_constraints_evaluated"
            ],
            "status": "APPLICATION_DIAGNOSTICS_VERIFIED",
        }
    )
    summary.update(
        {
            "diagnostic_package_hash": package_hash,
            "issues_total": package_summary["issues_total"],
            "issues_by_classification": package_summary[
                "issues_by_classification"
            ],
            "requirements_evaluated": package_coverage[
                "requirements_evaluated"
            ],
            "constraints_evaluated": package_coverage[
                "shacl_constraints_evaluated"
            ],
        }
    )
    determinism["diagnostic_package_hash"] = package_hash
    determinism["canonical_hashes"] = [package_hash] * determinism[
        "determinism_runs"
    ]
    _write(attestation_path, attestation)
    _write(summary_path, summary)
    _write(determinism_path, determinism)


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
    store = controlled_governance_store_for_test_harness(
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

    replay_workspace = controlled_governance_workspace_for_test_harness(authority)
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
            "upstream_phase03_diagnostic_package_hash": "0" * 64,
            "issues": authority.issues,
        }
    )
    stale_current = [authority]
    stale_workspace = controlled_governance_workspace_for_test_harness(
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
    app = controlled_governance_app_for_test_harness(store, csrf_value=token)
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
    workspace_dir = ROOT / "runtime_outputs/governance/controlled-workspace"
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    production_authority = load_production_phase03_authority(
        publication_package_directory=publication_package,
        publication_attestation_path=publication_attestation,
        phase01_artifact_directory=phase01,
        phase02_artifact_directory=phase02,
        phase03_artifact_directory=phase03_report,
        expected_commit_sha=commit_sha,
    )
    production_workspace = GovernanceWorkspace.initialize(production_authority)
    fixture = ControlledDiagnosticFixture.create()
    controlled_authority = controlled_governance_authority_for_test_harness(fixture)
    upstream_phase03_attestation_path = (
        phase03_report / "application-phase03-attestation.json"
    )
    upstream_phase03_attestation_before = upstream_phase03_attestation_path.read_bytes()
    upstream_phase03_before = (
        production_authority.upstream_phase03_diagnostic_package_hash
    )

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
        store, controlled_workspace, probes, _ = _run_governance(
            controlled_authority, workspace_dir
        )
        external_requests, service_workers = _http_and_browser_probes(store, probes)
        _verify_laundering_attacks(
            production_authority=production_authority,
            fixture=fixture,
            publication_package=publication_package,
            publication_attestation=publication_attestation,
            phase01=phase01,
            phase02=phase02,
            phase03=phase03_report,
            expected_commit_sha=commit_sha,
            probes=probes,
        )
        after_status = service.runtime_check()
        repository_after = after_status["live_graphdb_semantic_hash"]
        upstream_phase03_attestation_after = (
            upstream_phase03_attestation_path.read_bytes()
        )
        if upstream_phase03_attestation_after != upstream_phase03_attestation_before:
            raise RuntimeError("real upstream Phase03 attestation bytes changed")
        upstream_phase03_after = load_production_phase03_authority(
            publication_package_directory=publication_package,
            publication_attestation_path=publication_attestation,
            phase01_artifact_directory=phase01,
            phase02_artifact_directory=phase02,
            phase03_artifact_directory=phase03_report,
            expected_commit_sha=commit_sha,
        ).upstream_phase03_diagnostic_package_hash
        if (
            production_authority.upstream_phase03_attestation_sha256
            != hashlib.sha256(upstream_phase03_attestation_after).hexdigest()
        ):
            raise RuntimeError("real upstream Phase03 physical binding changed")
        controlled_state = controlled_workspace.reconstruct()
        controlled_summary = {
            "fixture_type": fixture.fixture_type,
            "test_only": fixture.test_only,
            "production_authority": fixture.production_authority,
            "controlled_fixture_hash": fixture.controlled_fixture_hash,
            "controlled_fixture_diagnostic_package_hash": (
                fixture.controlled_fixture_diagnostic_package_hash
            ),
            "controlled_fixture_status": fixture.status,
            "diagnostic_issues": len(controlled_authority.issues),
            "proposals_created": len(controlled_state["proposals"]),
            "proposals_submitted": sum(
                proposal["status"] != "DRAFT"
                for proposal in controlled_state["proposals"]
            ),
            "reviews_approved": sum(
                decision["decision"] == "APPROVE_FOR_AMENDMENT"
                for decision in controlled_state["review_decisions"]
            ),
            "reviews_rejected": sum(
                decision["decision"] == "REJECT"
                for decision in controlled_state["review_decisions"]
            ),
            "reviews_deferred": sum(
                decision["decision"] == "DEFER"
                for decision in controlled_state["review_decisions"]
            ),
            "amendment_requests": len(
                controlled_state["approved_amendment_requests"]
            ),
            "status": "PASS",
        }
        attestation = build_application_phase04_attestation(
            commit_sha=commit_sha,
            upstream_verification_mode="LOCAL_LICENSED",
            authority=production_authority,
            production_workspace=production_workspace.value,
            controlled_scenario_summary=controlled_summary,
            probes=probes,
            repository_before_hash=repository_before,
            repository_after_hash=repository_after,
            upstream_phase03_hash_before=upstream_phase03_before,
            upstream_phase03_hash_after=upstream_phase03_after,
        )
        report = ROOT / "runtime_reports/governance" / publication_hash
        documents = {
            "application-phase04-attestation.json": attestation,
            "governance-summary.json": {
                "contract_version": "1.0",
                "production_workspace": production_workspace.value,
                "production_workspace_hash": attestation[
                    "production_workspace_hash"
                ],
                "production_workspace_revision": attestation[
                    "production_workspace_revision"
                ],
                "production_issues_total": attestation[
                    "upstream_phase03_issues_total"
                ],
                "production_proposals_created": attestation[
                    "production_proposals_created"
                ],
                "production_reviews_approved": attestation[
                    "production_reviews_approved"
                ],
                "production_reviews_rejected": attestation[
                    "production_reviews_rejected"
                ],
                "production_reviews_deferred": attestation[
                    "production_reviews_deferred"
                ],
                "production_amendment_requests": attestation[
                    "production_amendment_requests"
                ],
                "controlled_scenario_summary": controlled_summary,
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
                **production_authority.binding,
                "status": "PASS",
            },
            "security-summary.json": {
                "contract_version": "1.0",
                "probe_authority_mode": "CONTROLLED_TEST_FIXTURE",
                "production_authority": False,
                "test_only": True,
                "probes": probes,
                "external_requests": external_requests,
                "service_workers": service_workers,
                "status": "PASS",
            },
        }
        if controlled_summary["amendment_requests"] != controlled_summary[
            "reviews_approved"
        ]:
            raise RuntimeError("amendment aggregation mismatch")
        for name, value in documents.items():
            _write(report / name, value)
        verified = verify_application_phase04_artifact(
            report,
            publication_package_directory=publication_package,
            publication_attestation_path=publication_attestation,
            publication_scenario="full-confirmation",
            phase01_artifact_directory=phase01,
            phase02_artifact_directory=phase02,
            phase03_artifact_directory=phase03_report,
            expected_commit_sha=commit_sha,
            expected_workspace_hash=production_workspace.value["workspace_hash"],
        )
        print(
            json.dumps(
                {
                    **verified,
                    "repository_before": repository_before,
                    "repository_after": repository_after,
                    "upstream_phase03_before": upstream_phase03_before,
                    "upstream_phase03_after": upstream_phase03_after,
                    "probe_count": len(probes),
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        cleanup_failure: Exception | None = None
        if imported:
            try:
                setup.delete_generated_repository(binding.repository_id)
            except GraphDBClientError as exc:
                cleanup_failure = exc
        cleanup = phase01_harness._compose(
            project, files, "down", "-v", "--remove-orphans", check=False
        )
        if cleanup.returncode != 0 and cleanup_failure is None:
            cleanup_failure = RuntimeError("Phase04 Compose cleanup failed")
        override.unlink(missing_ok=True)
        if generated_license is not None:
            generated_license.unlink(missing_ok=True)
        if cleanup_failure is not None:
            raise RuntimeError(
                "Phase04 integration cleanup failed"
            ) from cleanup_failure


if __name__ == "__main__":
    raise SystemExit(main())
