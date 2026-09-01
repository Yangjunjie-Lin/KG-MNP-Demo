from __future__ import annotations

import hashlib
import json
import subprocess
from importlib import resources
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef

from kg_mnp.contracts.catalog import ContractCatalog
from kg_mnp.semantic_kernel.packaging.archive import archive_bytes, verify_kgop
from kg_mnp.semantic_kernel.packaging.verifier import verify_package
from kg_mnp.semantic_kernel.policy import load_compiler_policy
from kg_mnp.semantic_kernel.rdf.canonical import canonical_ntriples
from kg_mnp.semantic_kernel.rdf.skolem import skolemize_graph
from kg_mnp.semantic_kernel.snapshot import build_compiler_snapshot

ROOT = Path(__file__).resolve().parents[2]


def test_prompt04_public_schema_bytes_are_preserved() -> None:
    raw = subprocess.run(
        ["git", "show", "eccc5092831503974c8aa54f158e6674445b1cb4:src/kg_mnp/contracts/catalog.json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    historical = json.loads(raw)
    package = resources.files("kg_mnp.contracts")
    assert len(historical["contracts"]) == 59
    for row in historical["contracts"]:
        assert hashlib.sha256(package.joinpath(row["resource_path"]).read_bytes()).hexdigest() == row["sha256"]
    assert len(ContractCatalog.load().specs) == 83


def test_policy_snapshot_and_structural_skolemization_are_deterministic() -> None:
    policy = load_compiler_policy()
    assert len(policy["supported_candidate_types"]) == 25
    assert all(value > 0 for value in policy["resource_limits"].values())
    assert build_compiler_snapshot(policy) == build_compiler_snapshot(policy)
    left = Graph()
    left.add((URIRef("urn:test:s"), URIRef("urn:test:p"), BNode("random-left")))
    left.add((next(left.objects()), URIRef("urn:test:q"), Literal("value")))
    right = Graph()
    right.add((BNode("random-right"), URIRef("urn:test:q"), Literal("value")))
    right.add((URIRef("urn:test:s"), URIRef("urn:test:p"), next(right.subjects())))
    assert canonical_ntriples(skolemize_graph(left)) == canonical_ntriples(skolemize_graph(right))


def test_minimal_validated_unpublished_package_and_archive(prompt05_case: dict, tmp_path: Path) -> None:
    plan = prompt05_case["plan"]
    attestation = prompt05_case["attestation"]
    result = prompt05_case["result"]
    assert attestation["status"] == "VALID"
    assert len(plan["candidate_dispatch"]) == 9
    verified = verify_package(result.package_directory)
    assert verified["package_id"] == result.package_id
    manifest = json.loads((result.package_directory / "ontology-package.json").read_bytes())
    assert manifest["package_status"] == "VALIDATED_UNPUBLISHED"
    first = archive_bytes(result.package_directory)
    second = archive_bytes(result.package_directory)
    assert first == second
    archive = tmp_path / "minimal.kgop"
    archive.write_bytes(first)
    assert verify_kgop(archive)["status"] == "VALID"
