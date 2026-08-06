from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef

from kg_mnp_demo.compilation.owl_consistency import load_ontology_graph
from kg_mnp_demo.compilation.shacl_validation import validate_abox
from ._helpers import build


MNP = Namespace("https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#")


def test_shacl_report_conforms(tmp_path):
    _, manifest, _ = build(tmp_path)
    assert manifest["shacl_status"] == "CONFORMS"
    assert manifest["shacl_violation_count"] == 0


def test_shacl_violation_is_reported_with_stable_result_ids():
    graph = Graph()
    graph.add((URIRef("urn:kg-mnp:audit:missing-case-id"), RDF.type, MNP.MNPCase))
    first, _, _, _ = validate_abox(graph, load_ontology_graph())
    second, _, _, _ = validate_abox(graph, load_ontology_graph())

    assert first["status"] == "VIOLATION"
    assert first["violation_count"] > 0
    assert first == second
    assert all(
        item["result_id"].startswith("urn:kg-mnp:shacl-result:")
        for item in first["results"]
    )


def test_shacl_warnings_and_info_are_recorded_without_becoming_violations():
    graph = Graph()
    evidence = URIRef("urn:kg-mnp:audit:evidence")
    graph.add((evidence, RDF.type, MNP.EvidenceRecord))
    graph.add((evidence, MNP.evidenceStatus, Literal("INVALID", datatype=XSD.string)))
    graph.add((evidence, MNP.hasSourceSystem, URIRef("urn:kg-mnp:audit:untyped-system")))

    report, _, _, _ = validate_abox(graph, Graph())

    assert report["status"] == "CONFORMS"
    assert report["violation_count"] == 0
    assert report["warning_count"] > 0
    assert report["info_count"] > 0
    assert len(report["results"]) >= report["warning_count"] + report["info_count"]
