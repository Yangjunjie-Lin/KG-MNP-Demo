from __future__ import annotations

from rdflib import BNode, Graph, Literal, URIRef

from kg_mnp.semantic_kernel.rdf.canonical import canonical_nquads, canonical_ntriples
from kg_mnp.semantic_kernel.rdf.serializers import deterministic_turtle
from kg_mnp.semantic_kernel.rdf.skolem import skolemize_graph


def test_canonical_nt_is_sorted_deduplicated_lf_and_round_trips() -> None:
    graph = Graph()
    graph.add((URIRef("urn:test:z"), URIRef("urn:test:p"), Literal("line\nquoted \"value\"")))
    graph.add((URIRef("urn:test:a"), URIRef("urn:test:p"), Literal("alpha")))
    data = canonical_ntriples(graph)
    assert data.endswith(b"\n") and b"\r" not in data and not data.startswith(b"\xef\xbb\xbf")
    assert data.splitlines() == sorted(data.splitlines())
    turtle = deterministic_turtle(graph)
    parsed = Graph().parse(data=turtle.decode(), format="turtle")
    assert canonical_ntriples(parsed) == data


def test_structural_skolemization_ignores_runtime_blank_node_labels() -> None:
    left = Graph()
    first = BNode("first-runtime-label")
    left.add((URIRef("urn:test:s"), URIRef("urn:test:p"), first))
    left.add((first, URIRef("urn:test:value"), Literal("same")))
    right = Graph()
    second = BNode("different-runtime-label")
    right.add((second, URIRef("urn:test:value"), Literal("same")))
    right.add((URIRef("urn:test:s"), URIRef("urn:test:p"), second))
    assert canonical_ntriples(skolemize_graph(left)) == canonical_ntriples(skolemize_graph(right))


def test_canonical_nquads_orders_by_graph_then_terms() -> None:
    quads = [
        (URIRef("urn:test:z"), URIRef("urn:test:p"), Literal("2"), URIRef("urn:test:g2")),
        (URIRef("urn:test:a"), URIRef("urn:test:p"), Literal("1"), URIRef("urn:test:g1")),
    ]
    assert canonical_nquads(quads) == canonical_nquads(reversed(quads))
    assert len(canonical_nquads([*quads, quads[0]]).splitlines()) == 2

