#!/usr/bin/env python3
from __future__ import annotations

import json
import base64
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "deploy" / "graphdb" / "docker-compose.integration.yml"
SCENARIO = "full-confirmation"


def _graph_bytes(dataset_bytes: bytes, graph_iri: str, mutate) -> bytes:
    from rdflib import Dataset, URIRef
    from kg_mnp_demo.compilation.rdf_canonical import canonical_ntriples

    dataset = Dataset()
    dataset.parse(data=dataset_bytes.decode("utf-8"), format="nquads")
    graph = dataset.graph(URIRef(graph_iri))
    mutate(graph)
    return canonical_ntriples(graph)


def _must_fail_verification(client, package_dir: Path, *, label: str) -> None:
    from kg_mnp_demo.graphdb.client import GraphDBClientError
    from kg_mnp_demo.graphdb.verifier import GraphDBVerificationError, verify_imported_repository

    try:
        verify_imported_repository(client, package_dir)
    except (GraphDBVerificationError, GraphDBClientError):
        return
    raise RuntimeError(f"live attack was accepted: {label}")


def _assert_default_dataset_semantics(client, repository_id: str) -> dict:
    """Freeze GraphDB's merged query view separately from physical storage."""

    snapshot = client.get_default_graph(repository_id)
    if snapshot.statement_count != 0:
        raise RuntimeError("physical default graph is not empty during semantics probe")
    result = client.sparql_select(
        repository_id,
        "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 1\n",
    )
    bindings = result.get("results", {}).get("bindings", [])
    if not isinstance(bindings, list) or not bindings:
        raise RuntimeError(
            "GraphDB ordinary default dataset did not expose named-graph data"
        )
    return {
        "ordinary_default_dataset_visible_named_data": True,
        "physical_default_graph_statement_count": snapshot.statement_count,
        "default_graph_http_status": snapshot.http_status,
        "default_graph_semantic_hash": snapshot.semantic_hash,
        "default_graph_content_type": snapshot.content_type,
    }


def _run_live_inference_regression(client, package_dir: Path, built: dict) -> dict:
    """Prove an inference-enabled repository is rejected by the verifier."""

    from rdflib import Dataset

    from kg_mnp_demo.graphdb.verifier import semantic_hash_nquads

    repository_id = built["manifest"]["repository_id"]
    config = built["files"]["repository/repository-config.ttl"]
    needle = b'graphdb:ruleset "empty"'
    if config.count(needle) != 1:
        raise RuntimeError("inference regression could not locate the empty ruleset")
    inference_config = config.replace(
        needle,
        b'graphdb:ruleset "rdfsplus-optimized"',
    )
    data = built["files"]["import/knowledge-graph.nq"]
    expected_explicit_hash = built["manifest"].get("assembled_dataset_semantic_hash")
    created = False
    try:
        create_status = client.create_repository(inference_config)
        created = True
        repository_info = client.inspect_repository(repository_id)
        ruleset = repository_info.get("params", {}).get("ruleset")
        if isinstance(ruleset, dict):
            ruleset = ruleset.get("value")
        if ruleset != "rdfsplus-optimized":
            raise RuntimeError("inference regression repository ruleset mismatch")
        import_status = client.import_nquads(repository_id, data)
        deadline = time.monotonic() + 120
        while True:
            explicit = client.export_nquads(repository_id, include_inferred=False)
            complete = client.export_nquads(repository_id, include_inferred=True)
            explicit_hash = semantic_hash_nquads(explicit)
            complete_hash = semantic_hash_nquads(complete)
            explicit_dataset = Dataset()
            explicit_dataset.parse(data=explicit.decode("utf-8"), format="nquads")
            complete_dataset = Dataset()
            complete_dataset.parse(data=complete.decode("utf-8"), format="nquads")
            explicit_count = len(
                list(explicit_dataset.quads((None, None, None, None)))
            )
            complete_count = len(
                list(complete_dataset.quads((None, None, None, None)))
            )
            explicit_ready = (
                expected_explicit_hash is None
                or explicit_hash == expected_explicit_hash
            )
            if (
                explicit_ready
                and complete_hash != explicit_hash
                and complete_count > explicit_count
            ):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "inference regression did not produce additional statements"
                )
            time.sleep(0.5)
        _must_fail_verification(
            client,
            package_dir,
            label="inference-enabled repository",
        )
        return {
            "ruleset": ruleset,
            "create_status": create_status,
            "import_status": import_status,
            "explicit_statement_count": explicit_count,
            "complete_statement_count": complete_count,
            "inferred_statement_count": complete_count - explicit_count,
            "explicit_semantic_hash": explicit_hash,
            "complete_semantic_hash": complete_hash,
            "verification_fail_closed": True,
        }
    finally:
        if created:
            client.delete_generated_repository(repository_id)


def _run_live_attack_regressions(client, package_dir: Path, built: dict) -> None:
    from rdflib import RDF, URIRef
    from rdflib.namespace import OWL

    repository_id = built["manifest"]["repository_id"]
    dataset_bytes = built["files"]["import/knowledge-graph.nq"]
    graphs = built["dataset"]["manifest"]["graph_iris"]

    client.replace_graph(
        repository_id,
        b"<urn:kg-mnp:attack:s> <urn:kg-mnp:attack:p> <urn:kg-mnp:attack:o> .\n",
        default=True,
    )
    try:
        _must_fail_verification(client, package_dir, label="physical default graph injection")
    finally:
        client.replace_graph(repository_id, b"", default=True)

    forbidden_triple = built["forbidden_assertions"].triples[0]
    client.replace_graph(
        repository_id,
        _graph_bytes(
            dataset_bytes,
            graphs["business_abox"],
            lambda graph: graph.add(forbidden_triple),
        ),
        graph_iri=graphs["business_abox"],
    )
    try:
        _must_fail_verification(client, package_dir, label="rejected assertion leakage")
    finally:
        client.replace_graph(
            repository_id,
            _graph_bytes(dataset_bytes, graphs["business_abox"], lambda graph: None),
            graph_iri=graphs["business_abox"],
        )

    def remove_one_review_decision(graph):
        decisions = sorted(
            graph.subjects(
                RDF.type,
                URIRef("https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#ReviewDecision"),
            ),
            key=str,
        )
        if not decisions:
            raise RuntimeError("live review attack fixture has no ReviewDecision")
        decision = decisions[0]
        graph.remove((decision, None, None))
        graph.remove((None, None, decision))

    client.replace_graph(
        repository_id,
        _graph_bytes(dataset_bytes, graphs["review_audit"], remove_one_review_decision),
        graph_iri=graphs["review_audit"],
    )
    try:
        _must_fail_verification(client, package_dir, label="review decision removal")
    finally:
        client.replace_graph(
            repository_id,
            _graph_bytes(dataset_bytes, graphs["review_audit"], lambda graph: None),
            graph_iri=graphs["review_audit"],
        )

    def replace_one_tbox_version(graph):
        ontologies = sorted(graph.subjects(RDF.type, OWL.Ontology), key=str)
        if not ontologies:
            raise RuntimeError("live TBox attack fixture has no ontology")
        ontology = ontologies[0]
        versions = list(graph.objects(ontology, OWL.versionIRI))
        if not versions:
            raise RuntimeError("live TBox attack fixture has no versionIRI")
        graph.remove((ontology, OWL.versionIRI, versions[0]))
        graph.add((ontology, OWL.versionIRI, URIRef("urn:kg-mnp:attack:wrong-version")))

    tbox_graph = built["tbox"]["modules"][0]["graph_iri"]
    client.replace_graph(
        repository_id,
        _graph_bytes(dataset_bytes, tbox_graph, replace_one_tbox_version),
        graph_iri=tbox_graph,
    )
    try:
        _must_fail_verification(client, package_dir, label="TBox version replacement")
    finally:
        client.replace_graph(
            repository_id,
            _graph_bytes(dataset_bytes, tbox_graph, lambda graph: None),
            graph_iri=tbox_graph,
        )

    def same_count_different_content(graph):
        values = sorted(
            graph.triples((None, None, None)),
            key=lambda triple: tuple(map(str, triple)),
        )
        if not values:
            raise RuntimeError("live same-count attack fixture is empty")
        subject, predicate, obj = values[0]
        graph.remove((subject, predicate, obj))
        graph.add(
            (
                subject,
                predicate,
                URIRef("urn:kg-mnp:attack:same-count-different-content"),
            )
        )

    client.replace_graph(
        repository_id,
        _graph_bytes(dataset_bytes, graphs["business_abox"], same_count_different_content),
        graph_iri=graphs["business_abox"],
    )
    try:
        _must_fail_verification(client, package_dir, label="same-count content replacement")
    finally:
        client.replace_graph(
            repository_id,
            _graph_bytes(dataset_bytes, graphs["business_abox"], lambda graph: None),
            graph_iri=graphs["business_abox"],
        )


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _authorities(scenario: str = SCENARIO) -> tuple[dict, ...]:
    from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
    from kg_mnp_demo.modeling.review_policy import load_default_review_policy

    dependencies = load_modeling_dependencies()
    return (
        _json(ROOT / "examples/modeling/inputs/partial-basic.json"),
        _json(ROOT / "examples/modeling/expected-proposals/partial-basic.proposal.json"),
        _json(ROOT / f"examples/review/expected-logs/{scenario}.log.json"),
        _json(ROOT / f"examples/review/expected-packages/{scenario}.package.json"),
        dependencies["ontology_baseline"], dependencies["mapping_rules"],
        dependencies["terminology_profile"], dependencies["proposal_policy"],
        load_default_review_policy(),
    )


COMPOSE_FILES: list[Path] = [COMPOSE]


def _compose(project: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    file_args: list[str] = []
    for compose_file in COMPOSE_FILES:
        file_args.extend(["-f", str(compose_file)])
    return subprocess.run(
        ["docker", "compose", "-p", project, *file_args, *args],
        cwd=ROOT, check=check, text=True,
    )


def _license_runtime_file(digest: str) -> tuple[Path | None, str]:
    license_file = os.environ.get("GRAPHDB_LICENSE_FILE")
    license_content = os.environ.get("GRAPHDB_LICENSE_CONTENT")
    license_b64 = os.environ.get("GRAPHDB_LICENSE_B64")
    provided = sum(value is not None and value != "" for value in (license_file, license_content, license_b64))
    if provided == 0:
        raise RuntimeError("failure_reason = EXTERNAL_GRAPHDB_LICENSE_MISSING")
    if provided > 1:
        raise RuntimeError(
            "failure_reason = EXTERNAL_GRAPHDB_LICENSE_SOURCE_AMBIGUOUS"
        )
    if license_file:
        path = Path(license_file).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError("failure_reason = EXTERNAL_GRAPHDB_LICENSE_FILE_UNREADABLE")
        return path, "FILE"
    raw: bytes
    source_type: str
    if license_content:
        raw = license_content.encode("utf-8")
        source_type = "CONTENT"
    else:
        try:
            raw = base64.b64decode(license_b64.encode("ascii"), validate=True)
        except Exception as exc:
            raise RuntimeError("failure_reason = EXTERNAL_GRAPHDB_LICENSE_B64_INVALID") from exc
        if not raw:
            raise RuntimeError("failure_reason = EXTERNAL_GRAPHDB_LICENSE_B64_INVALID")
        source_type = "B64"
    generated = ROOT / "runtime_outputs" / "graphdb" / f".{digest}.graphdb-license"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_bytes(raw)
    try:
        os.chmod(generated, 0o600)
    except OSError:
        pass
    return generated, source_type


def _cleanup_license_runtime_files(
    override_file: Path | None,
    generated_license_file: Path | None,
) -> None:
    if override_file is not None:
        while override_file in COMPOSE_FILES:
            COMPOSE_FILES.remove(override_file)
        override_file.unlink(missing_ok=True)
    if generated_license_file is not None:
        generated_license_file.unlink(missing_ok=True)


def _scan_non_sensitive_artifacts(*directories: Path) -> None:
    forbidden_names = {"license", "authorization", "cookie", "docker-env", ".env"}
    forbidden_terms = ("authorization:", "cookie:", "graphdb_license", "license_content", "license_b64")
    for directory in directories:
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            if any(term in path.name.lower() for term in forbidden_names):
                raise RuntimeError("sensitive artifact filename detected")
            try:
                text = path.read_text(encoding="utf-8").lower()
            except (UnicodeDecodeError, OSError):
                continue
            if any(term in text for term in forbidden_terms):
                raise RuntimeError("sensitive artifact content detected")


def main() -> int:
    from kg_mnp_demo.compilation.policy import load_compiler_policy
    from kg_mnp_demo.graphdb.attestation import build_import_attestation, write_import_attestation
    from kg_mnp_demo.graphdb.client import GraphDBClient
    from kg_mnp_demo.graphdb.importer import import_package
    from kg_mnp_demo.graphdb.package_builder import build_graphdb_import_package
    from kg_mnp_demo.graphdb.package_validator import validate_graphdb_import_package
    from kg_mnp_demo.graphdb.policy import load_graphdb_policy
    from kg_mnp_demo.graphdb.verifier import verify_imported_repository
    from kg_mnp_demo.graphdb._io import json_bytes

    authorities = _authorities()
    compilation = ROOT / f"examples/compilation/expected/{SCENARIO}"
    built = build_graphdb_import_package(compilation, *authorities, load_compiler_policy())
    digest = built["manifest"]["publication_semantic_hash"]
    project = "kgmnp-" + digest[:12]
    package_dir = ROOT / "runtime_outputs" / "graphdb" / digest
    report_dir = ROOT / "runtime_reports" / "graphdb" / digest
    from kg_mnp_demo.compilation.artifacts import write_artifact_set
    write_artifact_set(package_dir, built["files"], force=True)
    override_file: Path | None = None
    generated_license_file: Path | None = None
    license_source_type = "UNKNOWN"
    try:
        license_path, license_source_type = _license_runtime_file(digest)
    except RuntimeError as exc:
        print(json.dumps({"status": "NOT_VERIFIED", "failure_reason": str(exc)}, sort_keys=True))
        return 2
    if license_source_type in {"CONTENT", "B64"}:
        generated_license_file = license_path
    try:
        if license_path is not None:
            override_file = ROOT / "runtime_outputs" / "graphdb" / f".compose-license-{digest}.yml"
            override_file.write_text(
                "services:\n  graphdb:\n    volumes:\n"
                f"      - '{license_path.as_posix()}:/opt/graphdb/home/conf/graphdb.license:ro'\n",
                encoding="utf-8",
            )
            COMPOSE_FILES.append(override_file)
        validate_graphdb_import_package(
            package_dir, compilation_directory=compilation,
            cleaned_partial_data=authorities[0], proposal=authorities[1],
            final_review_decision_log=authorities[2], confirmed_modeling_package=authorities[3],
            ontology_baseline=authorities[4], mapping_rules=authorities[5],
            terminology_profile=authorities[6], proposal_policy=authorities[7],
            review_policy=authorities[8], compiler_policy=load_compiler_policy(),
        )
    except Exception:
        _cleanup_license_runtime_files(override_file, generated_license_file)
        raise
    client = GraphDBClient(timeout=10.0, retries=1)
    started_at = None
    imported: dict | None = None
    try:
        _compose(project, "up", "-d")
        deadline = time.monotonic() + 240
        while True:
            try:
                if client.health_check()["healthy"]:
                    break
            except Exception:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("GraphDB did not become healthy within 240 seconds")
            time.sleep(3)
        policy = load_graphdb_policy()
        readiness = client.verify_runtime_readiness(
            expected_product_version=policy["graphdb"]["product_version"]
        )
        version = readiness["version"]
        runtime_dir = report_dir / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "graphdb-version.json").write_bytes(json_bytes(version))
        started_at = __import__("kg_mnp_demo.graphdb.attestation", fromlist=["utc_now"]).utc_now()
        imported = import_package(client, package_dir)
        default_dataset_evidence = _assert_default_dataset_semantics(
            client,
            built["manifest"]["repository_id"],
        )
        verification_dir = report_dir / "verification"
        verification_dir.mkdir(parents=True, exist_ok=True)
        (verification_dir / "default-dataset-semantics.json").write_bytes(
            json_bytes(default_dataset_evidence)
        )
        repository_info = client.inspect_repository(built["manifest"]["repository_id"])
        (runtime_dir / "repository-info.json").write_bytes(json_bytes(repository_info))
        (runtime_dir / "import-response.json").write_bytes(json_bytes(imported))
        verification = verify_imported_repository(client, package_dir, report_directory=report_dir)
        rejection_authorities = _authorities("rejection")
        rejection_compilation = ROOT / "examples/compilation/expected/rejection"
        rejection_built = build_graphdb_import_package(
            rejection_compilation,
            *rejection_authorities,
            load_compiler_policy(),
        )
        rejection_package_dir = (
            ROOT / "runtime_outputs" / "graphdb" / rejection_built["manifest"]["publication_semantic_hash"]
        )
        write_artifact_set(rejection_package_dir, rejection_built["files"], force=True)
        validate_graphdb_import_package(
            rejection_package_dir,
            compilation_directory=rejection_compilation,
            cleaned_partial_data=rejection_authorities[0],
            proposal=rejection_authorities[1],
            final_review_decision_log=rejection_authorities[2],
            confirmed_modeling_package=rejection_authorities[3],
            ontology_baseline=rejection_authorities[4],
            mapping_rules=rejection_authorities[5],
            terminology_profile=rejection_authorities[6],
            proposal_policy=rejection_authorities[7],
            review_policy=rejection_authorities[8],
            compiler_policy=load_compiler_policy(),
        )
        import_package(client, rejection_package_dir)
        try:
            verify_imported_repository(client, rejection_package_dir)
            _run_live_attack_regressions(client, rejection_package_dir, rejection_built)
            verify_imported_repository(client, rejection_package_dir)
        finally:
            client.delete_generated_repository(rejection_built["manifest"]["repository_id"])
        inference_evidence = _run_live_inference_regression(
            client,
            rejection_package_dir,
            rejection_built,
        )
        (runtime_dir / "inference-regression.json").write_bytes(
            json_bytes(inference_evidence)
        )
        verification = verify_imported_repository(client, package_dir, report_directory=report_dir)
        policy = load_graphdb_policy()
        attestation = build_import_attestation(
            source_publication_id=built["manifest"]["publication_id"],
            source_compilation_id=built["manifest"]["source_compilation_id"],
            repository_config_hash=built["manifest"]["repository_config_byte_hash"],
            import_dataset_hash=built["manifest"]["assembled_dataset_semantic_hash"],
            export_dataset_hash=verification["export_semantic_hash"],
            expected_graph_count=len(built["manifest"]["named_graphs"]),
            actual_graph_count=len(verification["actual_graph_counts"]),
            expected_quad_count=built["manifest"]["assembled_quad_count"],
            actual_quad_count=verification["actual_quad_count"],
            verification=verification, graphdb_version=version,
            image_digest=policy["graphdb"]["image_digest_amd64"],
            repository_id=built["manifest"]["repository_id"],
            create_status=imported["create_status"], import_status=imported["import_status"],
            expected_named_graphs=built["manifest"]["named_graphs"],
            actual_named_graphs=list(verification["actual_graph_counts"]),
            license_state=readiness["license_state"],
            license_edition=readiness["edition"],
            license_source_type=license_source_type,
            started_at=started_at,
        )
        write_import_attestation(report_dir / "graphdb-import-attestation.json", attestation)
        _scan_non_sensitive_artifacts(package_dir, report_dir)
        client.delete_generated_repository(built["manifest"]["repository_id"])
        print(json.dumps({"status": "IMPORT_VERIFIED", "publication_id": built["manifest"]["publication_id"], "repository_id": built["manifest"]["repository_id"], "quad_count": verification["actual_quad_count"], "graph_count": len(verification["actual_graph_counts"]), "semantic_hash": verification["export_semantic_hash"]}, sort_keys=True))
        return 0
    finally:
        _compose(project, "down", "-v", "--remove-orphans", check=False)
        _cleanup_license_runtime_files(override_file, generated_license_file)


if __name__ == "__main__":
    raise SystemExit(main())
