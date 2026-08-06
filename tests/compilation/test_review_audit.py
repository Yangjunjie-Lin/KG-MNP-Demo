from rdflib import DCTERMS, RDF, Graph, Literal, Namespace, URIRef

from ._helpers import authorities, build


MNP = Namespace("https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#")


def test_rejected_items_are_audit_only(tmp_path):
    directory, manifest, _ = build(tmp_path, "rejection")
    assert manifest["release_status"] == "FORMALLY_VALIDATED"
    assert "REJECT" not in directory.joinpath("rdf/abox.nt").read_text(encoding="utf-8")
    assert "REJECT" in directory.joinpath("rdf/review-audit.nt").read_text(encoding="utf-8")

    decision_log = authorities("rejection")[2]
    graph = Graph()
    graph.parse(directory / "rdf" / "review-audit.nt", format="nt")
    log = URIRef(decision_log["decision_log_id"])
    assert (log, RDF.type, MNP.ReviewDecision) in graph
    assert next(graph.objects(log, DCTERMS.creator), None) is not None
    assert next(graph.objects(log, DCTERMS.relation), None) is not None
    for decision in decision_log["decisions"]:
        record = URIRef(decision["decision_id"])
        assert (record, RDF.type, MNP.ReviewDecision) in graph
        assert Literal(decision["decision"]) in graph.objects(record, MNP.reviewOutcomeCode)
        assert Literal(decision["rationale"]) in graph.objects(record, DCTERMS.description)
        assert next(graph.objects(record, DCTERMS.creator), None) is not None
        if decision.get("evidence_refs"):
            assert next(graph.objects(record, DCTERMS.references), None) is not None
