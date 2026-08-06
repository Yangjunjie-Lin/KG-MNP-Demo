from rdflib import RDF, SH, XSD, Graph, Literal, Namespace, URIRef

from kg_mnp_demo.compilation.owl_consistency import load_ontology_graph
from kg_mnp_demo.compilation.rdf_canonical import canonical_ntriples
from kg_mnp_demo.compilation.shacl_validation import (
    _deterministic_report_graph,
    _node,
    validate_abox,
)
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


def test_shacl_literal_value_preserved():
    graph = Graph()
    evidence = URIRef("urn:kg-mnp:audit:evidence")
    graph.add((evidence, RDF.type, MNP.EvidenceRecord))
    graph.add((evidence, MNP.evidenceStatus, Literal("INVALID", datatype=XSD.string)))

    report, report_graph, _, _ = validate_abox(graph, Graph())
    result = next(item for item in report["results"] if item["value"] is not None)
    assert result["value"] == {
        "term_type": "LITERAL",
        "lexical_form": "INVALID",
        "datatype_iri": str(XSD.string),
        "language": None,
    }

    value = next(report_graph.objects(URIRef(result["result_id"]), SH.value))
    assert isinstance(value, Literal)
    assert not isinstance(value, URIRef)
    assert str(value) == "INVALID"
    assert value.datatype == XSD.string

    parsed = Graph()
    parsed.parse(data=canonical_ntriples(report_graph).decode("utf-8"), format="nt")
    round_tripped = next(parsed.objects(URIRef(result["result_id"]), SH.value))
    assert isinstance(round_tripped, Literal)
    assert str(round_tripped) == "INVALID"
    assert round_tripped.datatype == XSD.string


def test_shacl_language_literal_preserved():
    source_graph = Graph()
    source_value = Literal("non conforme", lang="fr")
    projected = _node(source_graph, source_value)
    assert projected == {
        "term_type": "LITERAL",
        "lexical_form": "non conforme",
        "datatype_iri": str(RDF.langString),
        "language": "fr",
    }
    report = {
        "report_id": "urn:kg-mnp:shacl-report:" + "a" * 64,
        "conforms": True,
        "results": [
            {
                "result_id": "urn:kg-mnp:shacl-result:" + "b" * 64,
                "focus_node": {"term_type": "IRI", "value": "urn:kg-mnp:test:focus"},
                "result_path": None,
                "value": projected,
                "source_shape": None,
                "source_constraint_component": None,
                "severity": {"term_type": "IRI", "value": str(SH.Warning)},
                "message": "language-tagged value",
            }
        ],
    }
    rebuilt = _deterministic_report_graph(report)
    parsed = Graph()
    parsed.parse(data=canonical_ntriples(rebuilt).decode("utf-8"), format="nt")
    value = next(
        parsed.objects(URIRef(report["results"][0]["result_id"]), SH.value)
    )
    assert isinstance(value, Literal)
    assert str(value) == "non conforme"
    assert value.language == "fr"
    assert (value.datatype or RDF.langString) == RDF.langString
