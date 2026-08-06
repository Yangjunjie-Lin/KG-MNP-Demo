from rdflib import Graph, Literal, URIRef

from kg_mnp_demo.compilation.rdf_canonical import deterministic_turtle
from ._helpers import build


def test_turtle_is_byte_stable(tmp_path):
    first, _, _ = build(tmp_path / "one")
    second, _, _ = build(tmp_path / "two")
    assert first.joinpath("rdf/abox.ttl").read_bytes() == second.joinpath("rdf/abox.ttl").read_bytes()


def test_turtle_does_not_depend_on_rdf_insertion_order():
    triples = [
        (URIRef("urn:z"), URIRef("urn:p"), Literal("two")),
        (URIRef("urn:a"), URIRef("urn:p"), Literal("one")),
    ]
    first = Graph()
    second = Graph()
    for triple in triples:
        first.add(triple)
    for triple in reversed(triples):
        second.add(triple)
    assert deterministic_turtle(first) == deterministic_turtle(second)
