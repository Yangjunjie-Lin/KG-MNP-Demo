from rdflib import Graph, Literal, URIRef

from kg_mnp_demo.compilation.rdf_canonical import deterministic_trig
from ._helpers import build


def test_trig_is_byte_stable(tmp_path):
    first, _, _ = build(tmp_path / "one")
    second, _, _ = build(tmp_path / "two")
    assert first.joinpath("rdf/dataset.trig").read_bytes() == second.joinpath("rdf/dataset.trig").read_bytes()


def test_trig_does_not_depend_on_graph_or_triple_insertion_order():
    triples = [
        (URIRef("urn:z"), URIRef("urn:p"), Literal("two")),
        (URIRef("urn:a"), URIRef("urn:p"), Literal("one")),
    ]
    graph_one = Graph()
    graph_two = Graph()
    for triple in triples:
        graph_one.add(triple)
    for triple in reversed(triples):
        graph_two.add(triple)
    first = {URIRef("urn:graph:b"): graph_one, URIRef("urn:graph:a"): graph_two}
    second = {URIRef("urn:graph:a"): graph_two, URIRef("urn:graph:b"): graph_one}
    assert deterministic_trig(first) == deterministic_trig(second)
