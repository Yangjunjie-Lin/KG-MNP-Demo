from rdflib import OWL, RDF, URIRef

from kg_mnp_demo.compilation.abox_compiler import compile_abox
from kg_mnp_demo.compilation.owl_consistency import check_owl_consistency, load_ontology_graph
from ._helpers import authorities, build


def test_package_is_owl_consistent(tmp_path):
    _, manifest, _ = build(tmp_path)
    assert manifest["owl_consistency_status"] == "CONSISTENT"


def test_owl_inconsistency_is_not_accepted():
    values = authorities()
    graph, _ = compile_abox(values[3], values[1], values[4])
    graph.add((URIRef("urn:kg-mnp:audit:impossible"), RDF.type, OWL.Nothing))

    report = check_owl_consistency(
        graph,
        values[4],
        values[3]["package_semantic_hash"],
        ontology_graph=load_ontology_graph(),
    )

    assert report["status"] == "INCONSISTENT"
    assert report["consistent"] is False
