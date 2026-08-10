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
from rdflib import Dataset, Graph, URIRef

from kg_mnp_demo.application.attestation import build_application_attestation
from kg_mnp_demo.application.artifact_verifier import (
    verify_application_phase01_artifact,
)
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
        (
            "POST",
            f"/repositories/{repository_id}?timeout=5",
            b"INSERT DATA { <urn:attack:s> <urn:attack:p> <urn:attack:o> }",
            "application/sparql-query",
        ),
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


def _live_repository_tamper_attacks(
    setup: GraphDBClient,
    service: ApplicationService,
    repository_id: str,
) -> tuple[int, int]:
    """Mutate the live fixture and require ordinary startup to fail immediately."""

    original = setup.export_nquads(repository_id, include_inferred=False)
    baseline_statement_count = setup.count_repository_statements(repository_id)
    dataset = Dataset()
    dataset.parse(data=original.decode("utf-8"), format="nquads")
    selected = next(
        (
            (subject, predicate, obj, graph)
            for subject, predicate, obj, graph in dataset.quads(
                (None, None, None, None)
            )
            if isinstance(subject, URIRef)
            and isinstance(predicate, URIRef)
            and isinstance(obj, URIRef)
            and isinstance(graph, URIRef)
        ),
        None,
    )
    if selected is None:
        raise RuntimeError("live GraphDB fixture has no removable named-graph quad")
    subject, predicate, obj, graph = selected
    original_graph = Graph()
    for triple in dataset.graph(graph):
        original_graph.add(triple)
    removed_graph = Graph()
    for triple in original_graph:
        if triple != (subject, predicate, obj):
            removed_graph.add(triple)
    attack_triple = (
        URIRef("urn:kg-mnp:phase01-tamper:subject"),
        URIRef("urn:kg-mnp:phase01-tamper:predicate"),
        URIRef("urn:kg-mnp:phase01-tamper:object"),
    )
    replacement_graph = Graph()
    for triple in removed_graph:
        replacement_graph.add(triple)
    replacement_graph.add(attack_triple)

    def ntriples(value: Graph) -> bytes:
        serialized = value.serialize(format="nt")
        if isinstance(serialized, bytes):
            return serialized
        return serialized.encode("utf-8")

    attack_nquad = (
        f"{attack_triple[0].n3()} {attack_triple[1].n3()} "
        f"{attack_triple[2].n3()} {graph.n3()} .\n"
    ).encode("utf-8")
    original_graph_bytes = ntriples(original_graph)
    removed_graph_bytes = ntriples(removed_graph)
    replacement_graph_bytes = ntriples(replacement_graph)
    if len(removed_graph) != len(original_graph) - 1 or len(replacement_graph) != len(
        original_graph
    ):
        raise RuntimeError("live GraphDB tamper fixtures have invalid statement counts")

    def replace(data: bytes) -> None:
        setup.replace_graph(repository_id, data, graph_iri=str(graph))

    def restore() -> None:
        replace(original_graph_bytes)
        restored = service.runtime_check()
        if restored.get("status") != "APPLICATION_READY":
            raise RuntimeError("live GraphDB fixture restoration was not verified")

    attacks = (
        (
            lambda: setup.import_nquads(repository_id, attack_nquad),
            baseline_statement_count + 1,
        ),
        (
            lambda: replace(removed_graph_bytes),
            baseline_statement_count - 1,
        ),
        (
            lambda: replace(replacement_graph_bytes),
            baseline_statement_count,
        ),
    )
    blocked = 0
    for attack, expected_statement_count in attacks:
        try:
            attack()
            if (
                setup.count_repository_statements(repository_id)
                != expected_statement_count
            ):
                raise RuntimeError("live repository tamper was not established")
            try:
                service.runtime_check()
            except ApplicationError as exc:
                if exc.code != ErrorCode.APPLICATION_NOT_READY:
                    raise RuntimeError(
                        "live repository tamper produced the wrong startup failure"
                    ) from exc
                blocked += 1
            else:
                raise RuntimeError("live repository tamper passed runtime startup")
        finally:
            restore()
    return len(attacks), blocked


def main() -> int:
    package = ROOT / "runtime_outputs/publication/full-confirmation"
    manifest = _json(package / "publication-manifest.json")
    publication_hash = manifest["publication_semantic_hash"]
    attestation = ROOT / f"runtime_reports/publication/{publication_hash}/publication-attestation.json"
    graphdb_hash = manifest["graphdb_publication_semantic_hash"]
    graphdb_package = ROOT / f"runtime_outputs/graphdb/{graphdb_hash}"
    binding = PublicationBinding.verify(
        package,
        attestation,
        publication_scenario="full-confirmation",
    )
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
        registry = QueryRegistry.load()
        readonly = ReadOnlyGraphDBClient(timeout=8.0)
        service = ApplicationService(binding=binding, registry=registry, client=readonly)
        runtime_before = service.runtime_check()
        if runtime_before.get("status") != "APPLICATION_READY":
            raise RuntimeError("ordinary Application startup is not ready")
        expected_hash = runtime_before["expected_graphdb_semantic_hash"]
        before = runtime_before["live_graphdb_semantic_hash"]
        golden_count, golden_passed, fact_trace = _golden_http(service)
        attacks, blocked = _mutation_attacks(readonly, binding.repository_id, service)
        tamper_attacks, tamper_blocked = _live_repository_tamper_attacks(
            setup, service, binding.repository_id
        )
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
        runtime_after = service.runtime_check()
        if runtime_after.get("status") != "APPLICATION_READY":
            raise RuntimeError("final ordinary Application startup is not ready")
        if runtime_after["expected_graphdb_semantic_hash"] != expected_hash:
            raise RuntimeError("Application expected GraphDB hash changed during run")
        after = runtime_after["live_graphdb_semantic_hash"]
        report = ROOT / f"runtime_reports/application/{publication_hash}"
        attestation_payload = build_application_attestation(
            binding=binding,
            registry=registry,
            live_graphdb_semantic_hash_before=before,
            live_graphdb_semantic_hash_after=after,
            golden_query_count=golden_count,
            golden_query_passed=golden_passed,
            mutation_attack_count=attacks,
            mutation_attack_blocked=blocked,
            live_repository_tamper_attack_count=tamper_attacks,
            live_repository_tamper_attack_blocked=tamper_blocked,
            traceability_checks=traceability_checks,
            http_runtime={"bind_host": "127.0.0.1", "read_only": True, "golden_http_status": "PASS" if golden_count == golden_passed else "FAILED"},
            result_determinism=deterministic,
        )
        _write(report / "application-attestation.json", attestation_payload)
        _write(report / "query-registry-manifest.json", registry.manifest())
        _write(
            report / "golden-query-summary.json",
            {
                "contract_version": "1.0",
                "publication_id": binding.publication_id,
                "query_registry_hash": registry.document_hash,
                "golden_query_count": golden_count,
                "golden_query_passed": golden_passed,
                "status": "PASS" if golden_count == golden_passed else "FAILED",
            },
        )
        _write(
            report / "security-summary.json",
            {
                "contract_version": "1.0",
                "publication_id": binding.publication_id,
                "repository_id": binding.repository_id,
                "mutation_attack_count": attacks,
                "mutation_attack_blocked": blocked,
                "live_repository_tamper_attack_count": tamper_attacks,
                "live_repository_tamper_attack_blocked": tamper_blocked,
                "status": "PASS"
                if attacks == blocked and tamper_attacks == tamper_blocked
                else "FAILED",
            },
        )
        _write(
            report / "graphdb-before-after.json",
            {
                "contract_version": "1.0",
                "publication_id": binding.publication_id,
                "repository_id": binding.repository_id,
                "expected_graphdb_semantic_hash": expected_hash,
                "live_graphdb_semantic_hash_before": before,
                "live_graphdb_semantic_hash_after": after,
                "publication_authority_reconstruction": (
                    attestation_payload["publication_authority_reconstruction"]
                ),
                "repository_semantic_identity_verified": (
                    expected_hash == before == after
                ),
                "repository_unchanged": before == after,
            },
        )
        verified_artifact = verify_application_phase01_artifact(report)
        print(
            json.dumps(
                {
                    **verified_artifact,
                    "golden_query_count": golden_count,
                    "mutation_attack_count": attacks,
                    "live_repository_tamper_attack_count": tamper_attacks,
                },
                sort_keys=True,
            )
        )
        return 0 if attestation_payload["status"] == "APPLICATION_READONLY_VERIFIED" else 1
    finally:
        if imported:
            try:
                setup.delete_generated_repository(binding.repository_id)
            except Exception:
                pass
        cleanup_error: Exception | None = None
        try:
            cleanup = _compose(
                project,
                files,
                "down",
                "-v",
                "--remove-orphans",
                check=False,
            )
            if cleanup.returncode != 0:
                cleanup_error = RuntimeError(
                    "Application integration resource cleanup failed"
                )
        except Exception as exc:
            cleanup_error = exc
        finally:
            override.unlink(missing_ok=True)
            if generated_license is not None:
                generated_license.unlink(missing_ok=True)
        if cleanup_error is not None:
            raise RuntimeError(
                "Application integration resource cleanup failed"
            ) from cleanup_error


if __name__ == "__main__":
    raise SystemExit(main())
