from __future__ import annotations

import importlib

from rdflib import Dataset, URIRef

from kg_mnp_demo.compilation.policy import load_compiler_policy
from kg_mnp_demo.graphdb.package_builder import build_graphdb_import_package
from kg_mnp_demo.graphdb.rdf_semantics import graphdb_semantic_hash

from ._helpers import authorities, compilation


def _project_forbidden(*args):
    module = importlib.import_module("kg_mnp_demo.graphdb.forbidden_assertions")
    return module.project_forbidden_business_assertions(*args)


def test_rejected_candidate_projects_the_exact_business_rdf_assertion():
    values = authorities("rejection")

    projection = _project_forbidden(
        values[1], values[2], values[3], values[4]
    )

    rejected = [
        item for item in projection.records
        if item["decision_outcome"] == "REJECT"
    ]
    assert len(rejected) == 1
    assert rejected[0]["projection_status"] == "PROJECTED"
    assert rejected[0]["canonical_ntriples_line"].startswith(
        "<https://yangjunjie-lin.github.io/KG-MNP-Demo/data/modeled/"
    )
    assert "ReviewDecision" not in rejected[0]["canonical_ntriples_line"]
    assert rejected[0]["source_candidate_id"].startswith("urn:kg-mnp:candidate:")
    assert projection.statement_count == 1


def test_deferred_unresolved_issues_are_explicitly_not_applicable():
    values = authorities("deferred-review")

    projection = _project_forbidden(
        values[1], values[2], values[3], values[4]
    )

    assert projection.statement_count == 0
    assert projection.records
    assert all(item["projection_status"] == "NOT_APPLICABLE" for item in projection.records)
    assert {
        item["reason"] for item in projection.records
    } == {"UNRESOLVED_ISSUE_NO_FORMAL_ABOX_TRIPLE"}


def test_forbidden_assertions_are_in_the_reconstructed_package_closed_set():
    values = authorities("rejection")

    built = build_graphdb_import_package(
        compilation("rejection"), *values, load_compiler_policy()
    )

    assert "verification/expected/forbidden-business-assertions.nt" in built["files"]
    assert "verification/expected/forbidden-business-assertions.json" in built["files"]
    records = built["forbidden_assertions"].records
    assert sum(item["projection_status"] == "PROJECTED" for item in records) == 1
    query = built["query_suite"]["queries"]["09-no-rejected-business-facts"]
    assert "VALUES (?s ?p ?o)" in query
    assert records[0]["canonical_ntriples_line"].rsplit(" .", 1)[0] in query


def test_attacker_rehash_cannot_hide_an_exact_rejected_assertion():
    values = authorities("rejection")
    built = build_graphdb_import_package(
        compilation("rejection"), *values, load_compiler_policy()
    )
    dataset = Dataset()
    dataset.parse(
        data=built["files"]["import/knowledge-graph.nq"].decode("utf-8"),
        format="nquads",
    )
    triple = built["forbidden_assertions"].triples[0]
    business = built["dataset"]["manifest"]["graph_iris"]["business_abox"]
    dataset.graph(URIRef(business)).add(triple)
    attacked_quads = list(dataset.quads((None, None, None, None)))
    attacker_controlled_hash = graphdb_semantic_hash(attacked_quads)
    assert attacker_controlled_hash != built["manifest"]["assembled_dataset_semantic_hash"]

    rows = list(
        dataset.query(
            built["query_suite"]["queries"]["09-no-rejected-business-facts"]
        )
    )
    assert rows == [triple]
