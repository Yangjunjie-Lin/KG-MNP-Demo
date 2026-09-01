from __future__ import annotations

from rdflib import Graph, Literal, URIRef

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.semantic_kernel.rdf.dataset import build_named_dataset
from kg_mnp.semantic_kernel.security import assert_read_only_query
from kg_mnp.semantic_kernel.validators.competency_questions import (
    build_cq_test_plan,
    execute_cq_test_plan,
)


def _assertion(kind: str, *, boolean: bool | None = None, integer: int | None = None, strings: list[str] | None = None, digest: str | None = None) -> dict[str, object]:
    return {"assertion_type": kind, "boolean_value": boolean, "integer_value": integer, "string_values": strings or [], "semantic_hash": digest}


def _test(question: int, query_ref: str, query_type: str, assertions: list[dict[str, object]], requirement: str = "REQUIRED") -> dict[str, object]:
    return {
        "question_id": stable_urn("competency-question", {"question": question}),
        "requirement": requirement,
        "query_artifact_ref": query_ref,
        "query_type": query_type,
        "target_graph_roles": ["abox"],
        "expected_answer_shape": "TEST_ORACLE",
        "assertions": assertions,
        "resource_limits": [
            {"name": "max_query_characters", "value": 10000},
            {"name": "max_query_results", "value": 100},
            {"name": "max_query_seconds", "value": 10},
            {"name": "max_query_path_depth", "value": 4},
        ],
    }


def test_ask_select_construct_oracles_and_no_oracle_status() -> None:
    queries = {
        "ask.rq": b"ASK { ?s <urn:test:label> ?label }",
        "select.rq": b"SELECT ?s ?label WHERE { ?s <urn:test:label> ?label }",
        "construct.rq": b"CONSTRUCT { ?s <urn:test:label> ?label } WHERE { ?s <urn:test:label> ?label }",
        "optional.rq": b"SELECT ?s WHERE { ?s <urn:test:label> ?label }",
    }
    loader = queries.__getitem__
    tests = [
        _test(1, "ask.rq", "ASK", [_assertion("BOOLEAN_EQUALS", boolean=True)]),
        _test(2, "select.rq", "SELECT", [_assertion("MIN_ROW_COUNT", integer=1), _assertion("REQUIRED_BINDINGS", strings=["s", "label"])]),
        _test(3, "construct.rq", "CONSTRUCT", [_assertion("GRAPH_PATTERN_PRESENT", strings=["<urn:test:label>"])]),
        _test(4, "optional.rq", "SELECT", [], requirement="OPTIONAL"),
    ]
    plan = build_cq_test_plan(tests, query_loader=loader)
    graph = Graph()
    graph.add((URIRef("urn:test:entity"), URIRef("urn:test:label"), Literal("Entity")))
    _, nq, _, graph_iris = build_named_dataset(package_identity_basis="urn:kg-mnp:ontology-package:" + "a" * 64, graphs_by_role={"abox": graph})
    report = execute_cq_test_plan(plan, dataset_nquads=nq, query_loader=loader, graph_iris=graph_iris)
    statuses = {item["question_status"] for item in report["results"]}
    assert report["required_passed"] is True and report["status"] == "UNVERIFIED"
    assert statuses == {"PASSED", "UNVERIFIED"}


def test_query_security_rejects_mutation_service_remote_dataset_and_complexity() -> None:
    for query in (
        "INSERT DATA { <urn:s> <urn:p> <urn:o> }",
        "SELECT * WHERE { SERVICE <https://example.test/sparql> { ?s ?p ?o } }",
        "SELECT * FROM <https://example.test/remote> WHERE { ?s ?p ?o }",
        "SELECT * WHERE { ?s <urn:p>/<urn:q>/<urn:r> ?o }",
    ):
        try:
            assert_read_only_query(query, max_path_depth=1)
        except ValueError:
            pass
        else:  # pragma: no cover - explicit security assertion
            raise AssertionError(f"unsafe query accepted: {query}")
