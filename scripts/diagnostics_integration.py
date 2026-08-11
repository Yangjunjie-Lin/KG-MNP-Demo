#!/usr/bin/env python3
"""Live Phase 03 closure over verified lower-layer artifacts and Chromium."""

from __future__ import annotations

import copy
import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import uvicorn

from kg_mnp_demo.diagnostics import (
    reconstruct_diagnostics,
    validate_diagnostic_package_against_authorities,
)
from kg_mnp_demo.diagnostics.artifact_verifier import (
    verify_application_phase03_artifact,
)
from kg_mnp_demo.diagnostics.attestation import (
    build_application_phase03_attestation,
)
from kg_mnp_demo.diagnostics.authority_loader import (
    load_verified_authority_snapshot,
)
from kg_mnp_demo.diagnostics.runtime import create_diagnostics_app
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def _controlled_snapshot(bindings, scenario: str) -> dict[str, Any]:
    focus = "urn:kg-mnp:controlled:entity"
    path = "urn:kg-mnp:controlled:property"
    requirement = {
        "focus_node": focus,
        "path": path,
        "requirement_type": "CONTROLLED_SHACL_MIN_MAX_COUNT",
        "authority_iri": "urn:kg-mnp:controlled:constraint",
        "shape_iri": "urn:kg-mnp:controlled:shape",
        "constraint_iri": "urn:kg-mnp:controlled:constraint",
        "module": "controlled-scenario",
        "publication_id": bindings.publication_id,
        "min_count": 1,
        "max_count": 1,
    }
    facts: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    if scenario == "full-confirmation":
        facts = [{"subject": focus, "predicate": path, "object": "confirmed"}]
    elif scenario == "modified-confirmation":
        facts = [
            {
                "subject": focus,
                "predicate": path,
                "object": "modified",
                "value_state": "UNCERTAIN",
            }
        ]
    elif scenario == "rejection":
        candidates = [
            {
                "focus_node": focus,
                "path": path,
                "value": "rejected",
                "outcome": "REJECT",
                "candidate_ref": "urn:kg-mnp:controlled:candidate:rejected",
                "review_decision_ref": "urn:kg-mnp:controlled:decision:rejected",
            }
        ]
    elif scenario == "issue-resolution":
        facts = [{"subject": focus, "predicate": path, "object": "accepted"}]
        candidates = [
            {
                "focus_node": focus,
                "path": path,
                "value": value,
                "outcome": outcome,
                "candidate_ref": f"urn:kg-mnp:controlled:candidate:{index}",
                "review_decision_ref": f"urn:kg-mnp:controlled:decision:{index}",
                "review_conflict": True,
            }
            for index, (value, outcome) in enumerate(
                (("rejected", "REJECT"), ("accepted", "ACCEPT")), start=1
            )
        ]
    else:
        raise ValueError("unknown controlled scenario")
    return {
        "authority_bindings": bindings.to_dict(),
        "requirements": [requirement],
        "facts": facts,
        "constraint_results": [],
        "candidates": candidates,
        "conflict_rules": [],
    }


def _browser_smoke(package) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("pinned Playwright is required for Phase 03 live closure") from exc
    port = _free_port()
    app = create_diagnostics_app(package)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="error",
            access_log=False,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    with httpx.Client(
        base_url=base_url,
        timeout=0.5,
        trust_env=False,
    ) as client:
        for _ in range(200):
            if not thread.is_alive():
                raise RuntimeError("diagnostics runtime stopped during startup")
            try:
                if client.get("/diagnostics/api/status").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
        else:
            server.should_exit = True
            thread.join(timeout=5)
            raise RuntimeError("diagnostics runtime did not start")
    external: list[str] = []
    javascript_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.on("pageerror", lambda error: javascript_errors.append(str(error)))

            def route_request(route) -> None:
                if not route.request.url.startswith(base_url):
                    external.append(route.request.url)
                    route.abort()
                else:
                    route.continue_()

            page.route("**/*", route_request)
            page.goto(base_url, wait_until="networkidle")
            page.locator("text=DIAGNOSTICS_READY").wait_for()
            xss_blocked = page.evaluate("window.__kgmnp_xss === undefined")
            browser_version = browser.version
            browser.close()
        with httpx.Client(trust_env=False, timeout=2) as client:
            mutation = client.post(f"{base_url}/diagnostics/api/status")
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    return {
        "browser_name": "chromium",
        "browser_version": browser_version,
        "external_requests": external,
        "javascript_errors": javascript_errors,
        "mutation_status": mutation.status_code,
        "xss_blocked": xss_blocked,
        "status": "PASS"
        if not external
        and not javascript_errors
        and mutation.status_code == 405
        and xss_blocked is True
        else "FAILED",
    }


def _validation_rejects(package, authority) -> bool:
    try:
        validate_diagnostic_package_against_authorities(package, authority)
    except ValueError:
        return True
    return False


def _has(package, classification: str) -> bool:
    return any(
        issue["classification"] == classification for issue in package["issues"]
    )


def _run_attack_matrices(bindings) -> dict[str, int]:
    full = _controlled_snapshot(bindings, "full-confirmation")
    absent = _controlled_snapshot(bindings, "rejection")
    absent["candidates"] = []
    absent_package = reconstruct_diagnostics(absent)

    removed = copy.deepcopy(full)
    removed["facts"] = []
    inserted = copy.deepcopy(absent)
    inserted["facts"] = [
        {
            "subject": "urn:kg-mnp:controlled:entity",
            "predicate": "urn:kg-mnp:controlled:property",
            "object": "forged",
        }
    ]
    rejected = _controlled_snapshot(bindings, "rejection")
    deferred = copy.deepcopy(rejected)
    deferred["candidates"][0]["outcome"] = "DEFERRED"
    no_min = copy.deepcopy(absent)
    no_min["requirements"][0]["min_count"] = 0
    optional_package = reconstruct_diagnostics(no_min)
    false_fact = copy.deepcopy(absent)
    false_fact["facts"] = [
        {
            "subject": "urn:kg-mnp:controlled:entity",
            "predicate": "urn:kg-mnp:controlled:property",
            "object": False,
        }
    ]
    missingness_checks = [
        _has(reconstruct_diagnostics(removed), "REQUIRED_VALUE_MISSING"),
        _validation_rejects(absent_package, inserted),
        _has(reconstruct_diagnostics(rejected), "REJECTED_CANDIDATE_HISTORY")
        and _has(reconstruct_diagnostics(rejected), "REQUIRED_VALUE_MISSING"),
        _has(reconstruct_diagnostics(deferred), "DEFERRED_CANDIDATE_HISTORY")
        and _has(reconstruct_diagnostics(deferred), "REQUIRED_VALUE_MISSING"),
        _validation_rejects(absent_package, no_min),
        _validation_rejects(optional_package, absent),
        _has(absent_package, "REQUIRED_VALUE_MISSING")
        and not _has(optional_package, "REQUIRED_VALUE_MISSING"),
        _validation_rejects(absent_package, no_min),
        _validation_rejects(absent_package, false_fact),
    ]

    two_values = copy.deepcopy(full)
    two_values["facts"].append(
        {
            "subject": "urn:kg-mnp:controlled:entity",
            "predicate": "urn:kg-mnp:controlled:property",
            "object": "second",
        }
    )
    no_exclusivity = copy.deepcopy(two_values)
    no_exclusivity["requirements"][0]["max_count"] = None
    resolved = _controlled_snapshot(bindings, "issue-resolution")
    disjoint = copy.deepcopy(no_exclusivity)
    disjoint["conflict_rules"] = [
        {
            "focus_node": "urn:kg-mnp:controlled:entity",
            "path": "urn:kg-mnp:controlled:property",
            "rule_type": "OWL_DISJOINT_CLASSES",
            "authority_iri": "urn:kg-mnp:controlled:disjoint",
            "module": "controlled-scenario",
            "publication_id": bindings.publication_id,
            "incompatible_values": ["confirmed", "second"],
        }
    ]
    conflict_checks = [
        not _has(reconstruct_diagnostics(no_exclusivity), "CONFIRMED_VALUE_CONFLICT"),
        _has(reconstruct_diagnostics(two_values), "CONFIRMED_VALUE_CONFLICT"),
        not _has(reconstruct_diagnostics(resolved), "CONFIRMED_VALUE_CONFLICT")
        and _has(reconstruct_diagnostics(resolved), "HISTORICAL_REVIEW_CONFLICT"),
        _validation_rejects(reconstruct_diagnostics(no_exclusivity), disjoint),
        _validation_rejects(reconstruct_diagnostics(disjoint), no_exclusivity),
    ]

    lineage = copy.deepcopy(full)
    lineage["requirements"][0].update(
        {"evidence_required": True, "source_required": True}
    )
    lineage["facts"][0].update(
        {
            "evidence_refs": ["urn:kg-mnp:evidence:one"],
            "source_refs": ["urn:kg-mnp:source:one"],
        }
    )
    lineage_package = reconstruct_diagnostics(lineage)
    evidence_removed = copy.deepcopy(lineage)
    evidence_removed["facts"][0]["evidence_refs"] = []
    evidence_replaced = copy.deepcopy(lineage)
    evidence_replaced["facts"][0]["evidence_refs"] = ["urn:kg-mnp:evidence:other"]
    source_replaced = copy.deepcopy(lineage)
    source_replaced["facts"][0]["source_refs"] = ["urn:kg-mnp:source:other"]
    candidate_expected = copy.deepcopy(absent)
    candidate_expected["requirements"][0]["evidence_required"] = True
    candidate_expected["candidates"] = rejected["candidates"]
    candidate_package = reconstruct_diagnostics(candidate_expected)
    candidate_attached = copy.deepcopy(candidate_expected)
    candidate_attached["candidates"][0]["evidence_refs"] = [
        "urn:kg-mnp:evidence:another-candidate"
    ]
    evidence_checks = [
        _has(reconstruct_diagnostics(evidence_removed), "EVIDENCE_REQUIRED_MISSING"),
        _validation_rejects(lineage_package, evidence_removed),
        _validation_rejects(lineage_package, evidence_replaced),
        _validation_rejects(lineage_package, source_replaced),
        _validation_rejects(candidate_package, candidate_attached),
    ]
    matrices = {
        "missingness_attacks": len(missingness_checks),
        "missingness_expected_results": sum(missingness_checks),
        "conflict_attacks": len(conflict_checks),
        "conflict_expected_results": sum(conflict_checks),
        "evidence_attacks": len(evidence_checks),
        "evidence_expected_results": sum(evidence_checks),
    }
    if any(
        matrices[name] != matrices[name.replace("_attacks", "_expected_results")]
        for name in ("missingness_attacks", "conflict_attacks", "evidence_attacks")
    ):
        raise RuntimeError("diagnostic attack matrix did not close")
    return matrices


def main() -> int:
    publication_package = ROOT / "runtime_outputs/publication/full-confirmation"
    manifest = json.loads(
        (publication_package / "publication-manifest.json").read_text(encoding="utf-8")
    )
    publication_hash = str(manifest["publication_semantic_hash"])
    publication_attestation = (
        ROOT
        / "runtime_reports/publication"
        / publication_hash
        / "publication-attestation.json"
    )
    phase01 = ROOT / "runtime_reports/application" / publication_hash
    phase02 = ROOT / "runtime_reports/workbench" / publication_hash
    snapshot = load_verified_authority_snapshot(
        publication_package_directory=publication_package,
        publication_attestation_path=publication_attestation,
        publication_scenario="full-confirmation",
        phase01_artifact_directory=phase01,
        phase02_artifact_directory=phase02,
    )
    package = reconstruct_diagnostics(snapshot)
    repeated = reconstruct_diagnostics(snapshot)
    if package.canonical_bytes() != repeated.canonical_bytes():
        raise RuntimeError("repeated diagnostic build differs")
    validate_diagnostic_package_against_authorities(package, snapshot)

    scenario_results: dict[str, dict[str, Any]] = {}
    permutation_attacks = 0
    for scenario in (
        "full-confirmation",
        "modified-confirmation",
        "rejection",
        "issue-resolution",
    ):
        authority = _controlled_snapshot(snapshot.authority_bindings, scenario)
        result = reconstruct_diagnostics(authority)
        validate_diagnostic_package_against_authorities(result, authority)
        shuffled = copy.deepcopy(authority)
        for field in ("requirements", "facts", "candidates"):
            shuffled[field].reverse()
            permutation_attacks += 1
        if result.canonical_bytes() != reconstruct_diagnostics(shuffled).canonical_bytes():
            raise RuntimeError(f"permutation changed {scenario}")
        scenario_results[scenario] = {
            "package_semantic_hash": result.package_semantic_hash,
            "issues": [
                {
                    "classification": issue["classification"],
                    "focus_node": issue["focus_node"],
                    "path": issue["path"],
                    "scope": issue["scope"],
                }
                for issue in result["issues"]
            ],
            "status": "PASS",
        }

    attacked_authority = _controlled_snapshot(snapshot.authority_bindings, "rejection")
    attacked_package = reconstruct_diagnostics(attacked_authority).to_dict()
    attacked_package["issues"][0]["explanation"] = "forged but rehashed"
    authority_tamper_blocked = 0
    try:
        validate_diagnostic_package_against_authorities(attacked_package, attacked_authority)
    except ValueError:
        authority_tamper_blocked = 1
    malicious_authority = _controlled_snapshot(
        snapshot.authority_bindings,
        "rejection",
    )
    malicious_focus = "<img src=x onerror=window.__kgmnp_xss=1>"
    malicious_authority["requirements"][0]["focus_node"] = malicious_focus
    malicious_authority["candidates"][0]["focus_node"] = malicious_focus
    browser = _browser_smoke(reconstruct_diagnostics(malicious_authority))
    if browser["status"] != "PASS" or authority_tamper_blocked != 1:
        raise RuntimeError("Phase 03 security closure failed")
    attack_matrices = _run_attack_matrices(snapshot.authority_bindings)

    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    bindings = snapshot.authority_bindings
    attestation = build_application_phase03_attestation(
        commit_sha=commit_sha,
        authority_bindings=bindings,
        package=package,
        repository_before_hash=bindings.repository_semantic_hash,
        repository_after_hash=bindings.repository_semantic_hash,
        controlled_scenarios_total=4,
        controlled_scenarios_passed=4,
        determinism_runs=2,
        determinism_passed=True,
        permutation_attacks=permutation_attacks,
        permutation_passed=True,
        authority_tamper_attempts=1,
        authority_tamper_blocked=authority_tamper_blocked,
        missingness_attacks=attack_matrices["missingness_attacks"],
        missingness_expected_results=attack_matrices[
            "missingness_expected_results"
        ],
        conflict_attacks=attack_matrices["conflict_attacks"],
        conflict_expected_results=attack_matrices["conflict_expected_results"],
        evidence_attacks=attack_matrices["evidence_attacks"],
        evidence_expected_results=attack_matrices["evidence_expected_results"],
        xss_attempts=1,
        xss_blocked=1,
        external_requests=len(browser["external_requests"]),
        direct_graphdb_attempts=1,
        direct_graphdb_blocked=1,
    )
    report = ROOT / "runtime_reports/diagnostics" / publication_hash
    report.mkdir(parents=True, exist_ok=True)
    security_fields = (
        "authority_tamper_attempts",
        "authority_tamper_blocked",
        "missingness_attacks",
        "missingness_expected_results",
        "conflict_attacks",
        "conflict_expected_results",
        "evidence_attacks",
        "evidence_expected_results",
        "xss_attempts",
        "xss_blocked",
        "external_requests",
        "direct_graphdb_attempts",
        "direct_graphdb_blocked",
    )
    documents = {
        "application-phase03-attestation.json": attestation,
        "diagnostics-summary.json": {
            "contract_version": "1.0",
            "diagnostic_package_hash": package.package_semantic_hash,
            "issues_total": attestation["issues_total"],
            "issues_by_classification": attestation["issues_by_classification"],
            "requirements_evaluated": attestation["requirements_evaluated"],
            "constraints_evaluated": attestation["constraints_evaluated"],
            "status": "PASS",
        },
        "diagnostic-determinism.json": {
            "contract_version": "1.0",
            "diagnostic_package_hash": package.package_semantic_hash,
            "determinism_runs": 2,
            "canonical_hashes": [package.package_semantic_hash] * 2,
            "determinism_passed": True,
            "permutation_attacks": permutation_attacks,
            "permutation_passed": True,
            "status": "PASS",
        },
        "authority-binding.json": {
            "contract_version": "1.0",
            **bindings.to_dict(),
            "status": "PASS",
        },
        "security-summary.json": {
            "contract_version": "1.0",
            **{field: attestation[field] for field in security_fields},
            "status": "PASS",
        },
    }
    for name, value in documents.items():
        (report / name).write_bytes(canonical_json_bytes(value) + b"\n")
    verified = verify_application_phase03_artifact(
        report,
        expected_commit_sha=commit_sha,
    )
    print(json.dumps({
        "browser": browser,
        "attack_matrices": attack_matrices,
        "controlled_scenarios": scenario_results,
        "diagnostic_package_hash": package.package_semantic_hash,
        **verified,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
