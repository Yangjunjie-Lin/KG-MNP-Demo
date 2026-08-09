#!/usr/bin/env python3
"""Licensed Application Phase 01 integration and read-only attestation harness."""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from kg_mnp_demo.application.attestation import build_application_attestation
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.http import create_app
from kg_mnp_demo.application.publication_binding import PublicationBinding
from kg_mnp_demo.application.query_registry import QueryRegistry
from kg_mnp_demo.application.readonly_client import ReadOnlyGraphDBClient
from kg_mnp_demo.application.service import ApplicationService
from kg_mnp_demo.compilation.manifest import json_bytes
from kg_mnp_demo.graphdb.client import GraphDBClient
from kg_mnp_demo.graphdb.importer import import_package
from kg_mnp_demo.graphdb.policy import load_graphdb_policy
from kg_mnp_demo.graphdb.rdf_semantics import graphdb_semantic_hash_nquads

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy/graphdb/docker-compose.integration.yml"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("expected JSON object")
    return value


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(payload))


def _license() -> tuple[Path, Path | None]:
    values = {
        "FILE": os.environ.get("GRAPHDB_LICENSE_FILE"),
        "CONTENT": os.environ.get("GRAPHDB_LICENSE_CONTENT"),
        "B64": os.environ.get("GRAPHDB_LICENSE_B64"),
    }
    supplied = [(kind, value) for kind, value in values.items() if value]
    if len(supplied) != 1:
        reason = "EXTERNAL_GRAPHDB_LICENSE_MISSING" if not supplied else "EXTERNAL_GRAPHDB_LICENSE_SOURCE_AMBIGUOUS"
        raise RuntimeError(f"failure_reason = {reason}")
    kind, value = supplied[0]
    if kind == "FILE":
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError("failure_reason = EXTERNAL_GRAPHDB_LICENSE_FILE_UNREADABLE")
        return path, None
    try:
        raw = value.encode("utf-8") if kind == "CONTENT" else base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as exc:
        raise RuntimeError("failure_reason = EXTERNAL_GRAPHDB_LICENSE_B64_INVALID") from exc
    if not raw:
        raise RuntimeError("failure_reason = EXTERNAL_GRAPHDB_LICENSE_B64_INVALID")
    generated = ROOT / "runtime_outputs/application/.graphdb-license"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_bytes(raw)
    try:
        os.chmod(generated, 0o600)
    except OSError:
        pass
    return generated, generated


def _compose(project: str, files: list[Path], *args: str, check: bool = True):
    file_args = [item for path in files for item in ("-f", str(path))]
    return subprocess.run(
        ["docker", "compose", "-p", project, *file_args, *args],
        cwd=ROOT,
        check=check,
        text=True,
    )


def _assert_port_free(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"required loopback port {port} is already in use") from exc


def _wait_graphdb(client: GraphDBClient) -> None:
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        try:
            if client.health_check()["healthy"]:
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("GraphDB did not become healthy within 240 seconds")


def _golden_http(service: ApplicationService) -> tuple[int, int, dict[str, Any]]:
    subscription = "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/modeled/2993a1403cabddd34da97cacad8c5aa55103903ab9d3a0d831bd9f989f2fc029"
    predicate = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#subscriptionStatusCode"
    candidate = "urn:kg-mnp:candidate:63de7ebf8435aedbba092b5cb7d83450eacb351ffbc96e9833bdcacc6c14a6e2"
    source = "urn:kg-mnp:source-record:703f296ce26afb5543514b90584f50bc062ca9e64436e3e5e49f9921148eab0d"
    requests = [
        ("/api/v1/health", {}, 200),
        ("/api/v1/ontology/classes", {"limit": 10}, 200),
        ("/api/v1/ontology/properties", {"limit": 10}, 200),
        ("/api/v1/ontology/term", {"iri": "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#ServiceSubscription"}, 200),
        ("/api/v1/entity", {"iri": subscription}, 200),
        ("/api/v1/entity/provenance", {"iri": subscription}, 200),
        ("/api/v1/fact", {"subject": subscription, "predicate": predicate, "object_type": "LITERAL", "object_value": "ACTIVE", "datatype_iri": "http://www.w3.org/2001/XMLSchema#string"}, 200),
        ("/api/v1/fact/provenance", {"subject": subscription, "predicate": predicate, "object_type": "LITERAL", "object_value": "ACTIVE", "datatype_iri": "http://www.w3.org/2001/XMLSchema#string"}, 200),
        ("/api/v1/review-trace", {"resource_id": candidate}, 200),
        ("/api/v1/source-trace", {"source_ref": source}, 200),
        ("/api/v1/entity", {"iri": "urn:kg-mnp:unknown"}, 200),
        ("/api/v1/entity", {"iri": "file:///etc/passwd"}, 422),
    ]
    passed = 0
    fact_trace: dict[str, Any] = {}
    with TestClient(create_app(service), raise_server_exceptions=False) as http:
        for path, params, expected_status in requests:
            response = http.get(path, params=params)
            if response.status_code != expected_status:
                continue
            payload = response.json()
            if expected_status == 200 and path != "/api/v1/health":
                if payload.get("publication_id") != service.binding.publication_id:
                    continue
                if payload.get("publication_semantic_hash") != service.binding.publication_semantic_hash:
                    continue
            if path == "/api/v1/fact/provenance" and expected_status == 200:
                fact_trace = payload
            passed += 1
    return len(requests), passed, fact_trace


def _mutation_attacks(client: ReadOnlyGraphDBClient, repository_id: str, service: ApplicationService) -> tuple[int, int]:
    attacks = [
        ("PUT", f"/repositories/{repository_id}/rdf-graphs/service", b"", "application/n-quads"),
        ("DELETE", f"/rest/repositories/{repository_id}", None, None),
        ("POST", f"/repositories/{repository_id}/statements", b"", "application/n-quads"),
        ("POST", f"/repositories/{repository_id}", b"INSERT DATA {}", "application/sparql-update"),
    ]
    blocked = 0
    for method, path, body, content_type in attacks:
        try:
            client._request(method, path, body=body, content_type=content_type)
        except ApplicationError as exc:
            blocked += exc.code == ErrorCode.READ_ONLY_POLICY_VIOLATION
    for method_name in ("create_repository", "delete_repository", "import_nquads", "replace_graph"):
        blocked += not hasattr(client, method_name)
    query_attacks = [
        "INSERT DATA { <urn:s> <urn:p> <urn:o> }",
        "DELETE WHERE { GRAPH ?g { ?s ?p ?o } }",
        "SELECT ?s WHERE { SERVICE <https://evil.example/sparql> { ?s ?p ?o } GRAPH ?g { ?s ?p ?o } }",
    ]
    for query in query_attacks:
        try:
            client.select(repository_id, query)
        except ApplicationError as exc:
            blocked += exc.code == ErrorCode.READ_ONLY_POLICY_VIOLATION
    with TestClient(create_app(service), raise_server_exceptions=False) as http:
        for method, path in (("POST", "/sparql"), ("PUT", "/api/v1/entity"), ("DELETE", "/api/v1/ontology/classes")):
            response = http.request(method, path, content=b"mutation")
            blocked += response.status_code == 405 and response.json().get("error", {}).get("code") == "READ_ONLY_POLICY_VIOLATION"
    return len(attacks) + 4 + len(query_attacks) + 3, int(blocked)


def main() -> int:
    package = ROOT / "runtime_outputs/publication/full-confirmation"
    manifest = _json(package / "publication-manifest.json")
    publication_hash = manifest["publication_semantic_hash"]
    attestation = ROOT / f"runtime_reports/publication/{publication_hash}/publication-attestation.json"
    graphdb_hash = manifest["graphdb_publication_semantic_hash"]
    graphdb_package = ROOT / f"runtime_outputs/graphdb/{graphdb_hash}"
    binding = PublicationBinding.verify(package, attestation)
    if graphdb_package.resolve() == package.resolve() or not graphdb_package.is_dir():
        raise RuntimeError("Stage 08 GraphDB package is unavailable")
    _assert_port_free(7200)
    license_path, generated_license = _license()
    override = ROOT / "runtime_outputs/application/.compose-license.yml"
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text(
        "services:\n  graphdb:\n    volumes:\n"
        f"      - '{license_path.as_posix()}:/opt/graphdb/home/conf/graphdb.license:ro'\n",
        encoding="utf-8",
    )
    files = [COMPOSE, override]
    project = "kgmnp-app-" + publication_hash[:12]
    # Repository creation is test-fixture setup and follows the frozen Stage 07
    # 60-second repository policy. Application queries still use <=10 seconds.
    setup = GraphDBClient(timeout=60.0, retries=0)
    imported = False
    try:
        _compose(project, files, "up", "-d")
        _wait_graphdb(setup)
        policy = load_graphdb_policy()
        setup.verify_runtime_readiness(expected_product_version=policy["graphdb"]["product_version"])
        import_package(setup, graphdb_package)
        imported = True
        if binding.repository_id not in setup.list_repositories():
            raise RuntimeError("publication repository lineage is unavailable")
        before = graphdb_semantic_hash_nquads(setup.export_nquads(binding.repository_id, include_inferred=False))
        registry = QueryRegistry.load()
        readonly = ReadOnlyGraphDBClient(timeout=8.0)
        service = ApplicationService(binding=binding, registry=registry, client=readonly)
        service.runtime_check()
        golden_count, golden_passed, fact_trace = _golden_http(service)
        attacks, blocked = _mutation_attacks(readonly, binding.repository_id, service)
        parameters = {"iri": "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/modeled/2993a1403cabddd34da97cacad8c5aa55103903ab9d3a0d831bd9f989f2fc029", "limit": 100, "offset": 0}
        first = service.run("business.entity", parameters)
        second = service.run("business.entity", parameters)
        deterministic = "PASS" if first["result_semantic_hash"] == second["result_semantic_hash"] else "FAILED"
        trace = fact_trace.get("traceability", {})
        traceability_checks = {
            "fact_level": "PASS" if trace.get("business_facts") else "FAILED",
            "review": "PASS" if trace.get("review") else "FAILED",
            "evidence": "PASS" if trace.get("evidence") else "FAILED",
            "source": "PASS" if trace.get("source") else "FAILED",
            "publication_lineage": "PASS" if trace.get("publication", {}).get("publication_id") == binding.publication_id else "FAILED",
        }
        after = graphdb_semantic_hash_nquads(setup.export_nquads(binding.repository_id, include_inferred=False))
        report = ROOT / f"runtime_reports/application/{publication_hash}"
        attestation_payload = build_application_attestation(
            binding=binding,
            registry=registry,
            graphdb_hash_before=before,
            graphdb_hash_after=after,
            golden_query_count=golden_count,
            golden_query_passed=golden_passed,
            mutation_attack_count=attacks,
            mutation_attack_blocked=blocked,
            traceability_checks=traceability_checks,
            http_runtime={"bind_host": "127.0.0.1", "read_only": True, "golden_http_status": "PASS" if golden_count == golden_passed else "FAILED"},
            result_determinism=deterministic,
        )
        _write(report / "application-attestation.json", attestation_payload)
        _write(report / "query-registry-manifest.json", registry.manifest())
        _write(report / "golden-query-summary.json", {"contract_version": "1.0", "golden_query_count": golden_count, "golden_query_passed": golden_passed})
        _write(report / "security-summary.json", {"contract_version": "1.0", "mutation_attack_count": attacks, "mutation_attack_blocked": blocked, "status": "PASS" if attacks == blocked else "FAILED"})
        _write(report / "graphdb-before-after.json", {"contract_version": "1.0", "graphdb_semantic_hash_before": before, "graphdb_semantic_hash_after": after, "equal": before == after})
        print(json.dumps({"status": attestation_payload["status"], "publication_id": binding.publication_id, "repository_id": binding.repository_id, "graphdb_semantic_hash_before": before, "graphdb_semantic_hash_after": after, "repository_unchanged": before == after, "golden_query_count": golden_count, "mutation_attack_count": attacks}, sort_keys=True))
        return 0 if attestation_payload["status"] == "APPLICATION_READONLY_VERIFIED" else 1
    finally:
        if imported:
            try:
                setup.delete_generated_repository(binding.repository_id)
            except Exception:
                pass
        _compose(project, files, "down", "-v", "--remove-orphans", check=False)
        override.unlink(missing_ok=True)
        if generated_license is not None:
            generated_license.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
