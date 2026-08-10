#!/usr/bin/env python3
"""Licensed Application Phase 02 live integration and attestation harness."""

from __future__ import annotations

import copy
import http.client
import importlib.util
import json
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn

import application_integration as phase01_harness
import workbench_browser_smoke
from kg_mnp_demo.application.artifact_verifier import (
    verify_application_phase01_artifact,
)
from kg_mnp_demo.application.http import create_app as create_phase01_app
from kg_mnp_demo.application.publication_binding import PublicationBinding
from kg_mnp_demo.application.query_registry import QueryRegistry
from kg_mnp_demo.application.readonly_client import ReadOnlyGraphDBClient
from kg_mnp_demo.application.service import ApplicationService
from kg_mnp_demo.graphdb.client import GraphDBClient
from kg_mnp_demo.graphdb.importer import import_package
from kg_mnp_demo.graphdb.policy import load_graphdb_policy
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.workbench.artifact_verifier import (
    verify_application_phase02_artifact,
)
from kg_mnp_demo.workbench.attestation import build_workbench_attestation
from kg_mnp_demo.workbench.binding import WorkbenchBinding
from kg_mnp_demo.workbench.errors import WorkbenchError
from kg_mnp_demo.workbench.manifest import (
    build_workbench_package,
    validate_workbench_package,
)
from kg_mnp_demo.workbench.relay import Phase01Relay
from kg_mnp_demo.workbench.runtime import create_workbench_app
from kg_mnp_demo.workbench.view_model import (
    assert_view_model_fidelity,
    build_view_model,
)


ROOT = Path(__file__).resolve().parents[1]
SUBSCRIPTION = "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/modeled/2993a1403cabddd34da97cacad8c5aa55103903ab9d3a0d831bd9f989f2fc029"
PREDICATE = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#subscriptionStatusCode"
XSS_ATTACKS = (
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "&#x6a;avascript:alert(1)",
    "%3Cscript%3Ealert(1)%3C/script%3E",
    "\"</div><script>alert(1)</script>",
    "urn:datatype:<script>alert(1)</script>",
    "en-<img-src-x>",
    "urn:source:<svg-onload-alert>",
)
SCENARIO_CANDIDATES = {
    "modified-confirmation": (
        "urn:kg-mnp:candidate:5b68a78bcd602a16e687f82b44570cf02bbc5df37e7e4b290accc6052db7014a",
        "MODIFY_AND_CONFIRM",
    ),
    "rejection": (
        "urn:kg-mnp:candidate:5b68a78bcd602a16e687f82b44570cf02bbc5df37e7e4b290accc6052db7014a",
        "REJECT",
    ),
    "issue-resolution": (
        "urn:kg-mnp:candidate:2409a3eb9d437128445d075ca8dbbb3c851aaacaced8c3f218d5997b6710b0b2",
        "CONFIRM",
    ),
}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("expected JSON object")
    return value


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(payload) + b"\n")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class _Server:
    def __init__(self, app, port: int):
        self.port = port
        self.server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
                access_log=False,
            )
        )
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self) -> None:
        self.thread.start()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                connection = http.client.HTTPConnection(
                    "127.0.0.1",
                    self.port,
                    timeout=1,
                )
                connection.request("GET", "/")
                response = connection.getresponse()
                response.read()
                connection.close()
                if response.status in {200, 404}:
                    return
            except OSError:
                pass
            time.sleep(0.1)
        raise RuntimeError("loopback HTTP service did not start")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=30)
        if self.thread.is_alive():
            raise RuntimeError("loopback HTTP service did not stop")


def _scenario_fixtures() -> dict[str, dict[str, Any]]:
    helper_path = ROOT / "tests/application/_phase01_helpers.py"
    spec = importlib.util.spec_from_file_location(
        "kg_mnp_phase01_fixture_helpers",
        helper_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Phase 01 controlled scenario fixtures are unavailable")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)

    fixtures: dict[str, dict[str, Any]] = {}
    for scenario, (candidate, expected_text) in SCENARIO_CANDIDATES.items():
        service = ApplicationService(
            binding=helpers.synthetic_binding(scenario),
            registry=QueryRegistry.load(),
            client=helpers.DatasetClient(scenario),
        )
        result = service.run(
            "review.trace",
            {"resource_id": candidate, "limit": 100, "offset": 0},
        )
        fixtures[scenario] = {
            "model": build_view_model(result, view_type="REVIEW_TRACE"),
            "expected_text": expected_text,
        }
    return fixtures


def _xss_model(service: ApplicationService) -> dict[str, Any]:
    result = service.run(
        "business.entity",
        {"iri": SUBSCRIPTION, "limit": 100, "offset": 0},
    )
    graph = {
        "variable": "graph",
        "term": {"term_type": "IRI", "iri": "urn:kg-mnp:graph:xss-fixture"},
    }
    direction = {
        "variable": "direction",
        "term": {
            "term_type": "LITERAL",
            "lexical_form": "OUTGOING",
            "datatype_iri": None,
            "language": None,
        },
    }
    subject = {
        "variable": "subject",
        "term": {"term_type": "IRI", "iri": SUBSCRIPTION},
    }
    predicate = {
        "variable": "predicate",
        "term": {"term_type": "IRI", "iri": "urn:kg-mnp:predicate:xss-fixture"},
    }
    result["results"] = [
        {
            "bindings": [
                copy.deepcopy(graph),
                copy.deepcopy(direction),
                copy.deepcopy(subject),
                copy.deepcopy(predicate),
                {
                    "variable": "object",
                    "term": {
                        "term_type": "LITERAL",
                        "lexical_form": attack,
                        "datatype_iri": (
                            XSS_ATTACKS[8] if index == 8 else "urn:datatype:text"
                        ),
                        "language": XSS_ATTACKS[9] if index == 9 else None,
                    },
                },
            ]
        }
        for index, attack in enumerate(XSS_ATTACKS)
    ]
    result["result_count"] = len(result["results"])
    result["result_semantic_hash"] = "b" * 64
    return build_view_model(result, view_type="ENTITY")


def _relay_attacks() -> tuple[int, int]:
    attacks = [
        ("GET", "http://evil.example/", {}),
        ("GET", "https://evil.example/", {}),
        ("GET", "//evil.example/", {}),
        ("GET", "/@evil.example", {}),
        ("GET", "/%68%74%74%70%3A%2F%2Fevil.example", {}),
        ("GET", "/%2568%2574%2574%2570%253A%252F%252Fevil.example", {}),
        ("GET", "/repositories/attacker", {}),
        ("GET", "\\\\evil.example\\share", {}),
        ("POST", "/api/v1/health", {}),
        ("PUT", "/api/v1/entity", {}),
        ("PATCH", "/api/v1/entity", {}),
        ("DELETE", "/api/v1/entity", {}),
        ("CONNECT", "/api/v1/health", {}),
        ("OPTIONS", "/api/v1/health", {}),
        ("GET", "/api/v1/entity", {"target": "http://evil.example"}),
    ]
    blocked = 0
    for method, path, parameters in attacks:
        try:
            Phase01Relay.validate_request(method, path, parameters)
        except WorkbenchError:
            blocked += 1
    return len(attacks), blocked


def _header_attacks(port: int) -> tuple[int, int]:
    attacks = (
        {"Host": "evil.example"},
        {"Host": f"127.0.0.1:{port}", "X-Forwarded-Host": "evil.example"},
        {
            "Host": f"127.0.0.1:{port}",
            "Connection": "Upgrade",
            "Upgrade": "websocket",
        },
    )
    blocked = 0
    for headers in attacks:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.putrequest("GET", "/workbench/api/status", skip_host=True)
        for key, value in headers.items():
            connection.putheader(key, value)
        connection.endheaders()
        response = connection.getresponse()
        response.read()
        connection.close()
        blocked += response.status in {400, 403, 404, 405, 421, 426}
    return len(attacks), int(blocked)


def _authority_attacks(
    binding: WorkbenchBinding,
    artifact_directory: Path,
) -> tuple[int, int]:
    baseline_health = phase01_harness._json(
        artifact_directory / "graphdb-before-after.json"
    )
    health = {
        "status": "APPLICATION_READY",
        "read_only": True,
        "publication_id": binding.publication_id,
        "publication_semantic_hash": binding.publication_semantic_hash,
        "repository_id": binding.repository_id,
        "expected_graphdb_semantic_hash": binding.repository_semantic_hash,
        "live_graphdb_semantic_hash": binding.repository_semantic_hash,
        "repository_semantic_identity_verified": True,
        "publication_authority_reconstruction": {
            "status": "PASS",
            "publication_id": binding.publication_id,
            "deterministic_reconstruction_match": True,
        },
    }
    attacked_fields = {
        "publication_id": "urn:kg-mnp:e2e-publication:" + "1" * 64,
        "publication_semantic_hash": "1" * 64,
        "repository_id": "kg-mnp-attacker",
        "live_graphdb_semantic_hash": "1" * 64,
        "status": "APPLICATION_NOT_READY",
    }
    blocked = 0
    for field, value in attacked_fields.items():
        attacked = copy.deepcopy(health)
        attacked[field] = value
        try:
            binding.verify_health(attacked)
        except WorkbenchError:
            blocked += 1
    attack_copy = ROOT / "runtime_outputs/workbench/authority-attack"
    if attack_copy.exists():
        shutil.rmtree(attack_copy)
    shutil.copytree(artifact_directory, attack_copy)
    attestation_path = attack_copy / "application-attestation.json"
    attestation = _json(attestation_path)
    attestation["query_registry_hash"] = "1" * 64
    _write(attestation_path, attestation)
    try:
        WorkbenchBinding.load(attack_copy)
    except WorkbenchError:
        blocked += 1
    shutil.rmtree(attack_copy)
    if baseline_health.get("repository_unchanged") is not True:
        raise RuntimeError("Phase 01 repository evidence is not closed")
    return len(attacked_fields) + 1, blocked


def main() -> int:
    package = ROOT / "runtime_outputs/publication/full-confirmation"
    publication_manifest = _json(package / "publication-manifest.json")
    publication_hash = publication_manifest["publication_semantic_hash"]
    stage08_attestation = (
        ROOT
        / "runtime_reports/publication"
        / publication_hash
        / "publication-attestation.json"
    )
    graphdb_hash = publication_manifest["graphdb_publication_semantic_hash"]
    graphdb_package = ROOT / "runtime_outputs/graphdb" / graphdb_hash
    publication_binding = PublicationBinding.verify(
        package,
        stage08_attestation,
        publication_scenario="full-confirmation",
    )
    phase01_artifact = ROOT / "runtime_reports/application" / publication_hash
    verify_application_phase01_artifact(phase01_artifact)
    binding = WorkbenchBinding.load(phase01_artifact)
    license_path, generated_license = phase01_harness._license()
    override = ROOT / "runtime_outputs/workbench/.compose-license.yml"
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text(
        "services:\n  graphdb:\n    volumes:\n"
        f"      - '{license_path.as_posix()}:/opt/graphdb/home/conf/graphdb.license:ro'\n",
        encoding="utf-8",
    )
    compose_files = [phase01_harness.COMPOSE, override]
    project = "kgmnp-workbench-" + publication_hash[:12]
    setup = GraphDBClient(timeout=60.0, retries=0)
    phase01_server: _Server | None = None
    workbench_server: _Server | None = None
    imported = False
    try:
        phase01_harness._assert_port_free(7200)
        phase01_harness._compose(project, compose_files, "up", "-d")
        phase01_harness._wait_graphdb(setup)
        setup.verify_runtime_readiness(
            expected_product_version=load_graphdb_policy()["graphdb"][
                "product_version"
            ]
        )
        import_package(setup, graphdb_package)
        imported = True
        readonly = ReadOnlyGraphDBClient(timeout=8.0)
        service = ApplicationService(
            binding=publication_binding,
            registry=QueryRegistry.load(),
            client=readonly,
        )
        runtime_before = service.runtime_check()
        repository_before = runtime_before["live_graphdb_semantic_hash"]

        phase01_port = _free_port()
        phase01_server = _Server(create_phase01_app(service), phase01_port)
        phase01_server.start()
        relay = Phase01Relay(
            f"http://127.0.0.1:{phase01_port}",
            binding,
        )

        package_dir = ROOT / "runtime_outputs/workbench/package"
        repeat_dir = ROOT / "runtime_outputs/workbench/package-repeat"
        manifest = build_workbench_package(package_dir, binding)
        repeat_manifest = build_workbench_package(repeat_dir, binding)
        if manifest != repeat_manifest:
            raise RuntimeError("workbench frontend build is not deterministic")
        validate_workbench_package(package_dir, binding)

        workbench_port = _free_port()
        workbench_server = _Server(
            create_workbench_app(
                binding=binding,
                relay=relay,
                package_directory=package_dir,
            ),
            workbench_port,
        )
        workbench_server.start()
        fact_result = service.run(
            "provenance.fact",
            {
                "subject": SUBSCRIPTION,
                "predicate": PREDICATE,
                "object": {
                    "term_type": "LITERAL",
                    "value": "ACTIVE",
                    "datatype_iri": "http://www.w3.org/2001/XMLSchema#string",
                    "language": None,
                },
                "limit": 100,
                "offset": 0,
            },
        )
        fact_view = build_view_model(fact_result, view_type="FACT_TRACE")
        assert_view_model_fidelity(fact_result, fact_view)
        browser = workbench_browser_smoke.run(
            f"http://127.0.0.1:{workbench_port}",
            xss_model=_xss_model(service),
            scenario_fixtures=_scenario_fixtures(),
        )
        relay_count, relay_blocked = _relay_attacks()
        header_count, header_blocked = _header_attacks(workbench_port)
        authority_count, authority_blocked = _authority_attacks(
            binding,
            phase01_artifact,
        )
        runtime_after = service.runtime_check()
        repository_after = runtime_after["live_graphdb_semantic_hash"]
        security = {
            "contract_version": "1.0",
            "xss_attack_count": browser["xss_attack_count"],
            "xss_attack_blocked": browser["xss_attack_blocked"],
            "relay_attack_count": relay_count + header_count,
            "relay_attack_blocked": relay_blocked + header_blocked,
            "authority_tamper_attack_count": authority_count,
            "authority_tamper_attack_blocked": authority_blocked,
            "direct_graphdb_access_attempt_count": browser[
                "direct_graphdb_access_attempt_count"
            ],
            "direct_graphdb_access_blocked_count": browser[
                "direct_graphdb_access_blocked_count"
            ],
        }
        security["status"] = "PASS" if (
            security["xss_attack_count"] == security["xss_attack_blocked"]
            and security["relay_attack_count"]
            == security["relay_attack_blocked"]
            and security["authority_tamper_attack_count"]
            == security["authority_tamper_attack_blocked"]
            and security["direct_graphdb_access_attempt_count"]
            == security["direct_graphdb_access_blocked_count"]
        ) else "FAILED"
        commit_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        attestation = build_workbench_attestation(
            commit_sha=commit_sha,
            binding=binding,
            frontend_build_hash=manifest["frontend_build_hash"],
            runtime_policy_hash=manifest["runtime_policy_hash"],
            repository_hash_before=repository_before,
            repository_hash_after=repository_after,
            browser=browser,
            security=security,
            result_fidelity_status="PASS",
            traceability_view_status=(
                "PASS"
                if fact_view["traceability"]["business_facts"]
                and fact_view["traceability"]["modeling"]
                and fact_view["traceability"]["review"]
                and fact_view["traceability"]["evidence"]
                and fact_view["traceability"]["source"]
                else "FAILED"
            ),
        )
        report = ROOT / "runtime_reports/workbench" / publication_hash
        if report.exists():
            shutil.rmtree(report)
        browser_artifact = {
            key: value
            for key, value in browser.items()
            if key not in {"blocked_network_probes", "content_security_policy"}
        }
        browser_artifact["blocked_network_probe_count"] = len(
            browser["blocked_network_probes"]
        )
        _write(report / "application-phase02-attestation.json", attestation)
        _write(report / "browser-smoke.json", browser_artifact)
        _write(report / "security-summary.json", security)
        _write(
            report / "binding-summary.json",
            {
                "contract_version": "1.0",
                "phase01_attestation_hash": binding.phase01_attestation_hash,
                "phase01_attestation_status": binding.phase01_attestation_status,
                "publication_id": binding.publication_id,
                "publication_semantic_hash": binding.publication_semantic_hash,
                "repository_semantic_hash": binding.repository_semantic_hash,
                "query_registry_hash": binding.query_registry_hash,
                "status": "PASS",
            },
        )
        _write(
            report / "graphdb-before-after.json",
            {
                "contract_version": "1.0",
                "expected": binding.repository_semantic_hash,
                "before": repository_before,
                "after": repository_after,
                "repository_unchanged": (
                    repository_before
                    == repository_after
                    == binding.repository_semantic_hash
                ),
                "status": (
                    "PASS"
                    if repository_before
                    == repository_after
                    == binding.repository_semantic_hash
                    else "FAILED"
                ),
            },
        )
        verified = verify_application_phase02_artifact(report)
        print(
            json.dumps(
                {
                    **verified,
                    "repository_hash_before": repository_before,
                    "repository_hash_after": repository_after,
                    "golden_scenario_count": browser["golden_scenario_count"],
                    "xss_attack_count": security["xss_attack_count"],
                    "relay_attack_count": security["relay_attack_count"],
                },
                sort_keys=True,
            )
        )
        return 0 if attestation["status"] == "APPLICATION_WORKBENCH_VERIFIED" else 1
    finally:
        if workbench_server is not None:
            workbench_server.stop()
        if phase01_server is not None:
            phase01_server.stop()
        if imported:
            try:
                setup.delete_generated_repository(publication_binding.repository_id)
            except Exception:
                pass
        phase01_harness._compose(
            project,
            compose_files,
            "down",
            "-v",
            "--remove-orphans",
            check=False,
        )
        override.unlink(missing_ok=True)
        if generated_license is not None:
            generated_license.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
