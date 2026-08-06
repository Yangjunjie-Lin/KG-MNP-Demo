from rdflib import DCTERMS, OWL, RDF, Graph, Namespace

from ._helpers import build


MNP = Namespace("https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#")


def test_every_confirmed_item_has_a_provenance_record(tmp_path):
    directory, manifest, _ = build(tmp_path)
    assert manifest["asserted_fact_count"] == manifest["provenance_record_count"] == 5
    text = directory.joinpath("rdf/modeling-provenance.nt").read_text(encoding="utf-8")
    assert text.count("owl#Axiom") == 5

    graph = Graph()
    graph.parse(directory / "rdf" / "modeling-provenance.nt", format="nt")
    records = set(graph.subjects(RDF.type, OWL.Axiom))
    assert len(records) == manifest["provenance_record_count"]
    for record in records:
        assert next(graph.objects(record, DCTERMS.source), None) is not None
        assert next(graph.objects(record, DCTERMS.relation), None) is not None
        assert next(graph.objects(record, MNP.usesMappingRule), None) is not None
        assert next(graph.objects(record, MNP.mapsSourceField), None) is not None
        assert next(graph.objects(record, MNP.hasModelingEvidence), None) is not None
        assert next(graph.objects(record, MNP.hasReviewDecision), None) is not None
        assert next(graph.objects(record, DCTERMS.description), None) is not None
