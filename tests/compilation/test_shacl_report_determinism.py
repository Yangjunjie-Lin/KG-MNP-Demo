from rdflib import RDF, BNode, Graph, URIRef

from kg_mnp_demo.compilation.shacl_validation import _node

from ._helpers import build


def test_shacl_report_is_deterministic(tmp_path):
    one, _, _ = build(tmp_path / "one")
    two, _, _ = build(tmp_path / "two")
    assert one.joinpath("shacl/report.json").read_bytes() == two.joinpath("shacl/report.json").read_bytes()


def test_structural_shacl_node_uses_content_hash_not_blank_node_label():
    def projected(label):
        graph = Graph()
        path = BNode(label)
        graph.add((path, RDF.first, URIRef("urn:kg-mnp:test:path")))
        graph.add((path, RDF.rest, RDF.nil))
        return _node(graph, path)

    first = projected("first-runtime-label")
    second = projected("different-runtime-label")
    assert first == second
    assert first == {
        "term_type": "STRUCTURAL_NODE",
        "stable_id": first["stable_id"],
    }
    assert first["stable_id"].startswith("urn:kg-mnp:shacl-node:")
    assert len(first["stable_id"].rsplit(":", 1)[-1]) == 64
