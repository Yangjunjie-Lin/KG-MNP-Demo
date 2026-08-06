import pytest
from rdflib import DCTERMS, RDF, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV

from ._helpers import authorities, build
from kg_mnp_demo.compilation.review_audit_compiler import compile_review_audit


MNP = Namespace("https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#")


def test_review_log_not_typed_as_decision():
    decision_log = authorities()[2]
    graph = compile_review_audit(decision_log, authorities()[3])
    log = URIRef(decision_log["decision_log_id"])
    assert (log, RDF.type, MNP.ReviewDecision) not in graph


def test_rejected_items_are_audit_only(tmp_path):
    directory, manifest, _ = build(tmp_path, "rejection")
    assert manifest["release_status"] == "FORMALLY_VALIDATED"
    assert "REJECT" not in directory.joinpath("rdf/abox.nt").read_text(encoding="utf-8")
    assert "REJECT" in directory.joinpath("rdf/review-audit.nt").read_text(encoding="utf-8")

    decision_log = authorities("rejection")[2]
    graph = Graph()
    graph.parse(directory / "rdf" / "review-audit.nt", format="nt")
    log = URIRef(decision_log["decision_log_id"])
    assert (log, RDF.type, MNP.ReviewDecision) not in graph
    assert (log, RDF.type, PROV.Entity) in graph
    session = URIRef(decision_log["review_session"]["session_id"])
    reviewer = URIRef(decision_log["reviewer"]["reviewer_id"])
    assert (session, RDF.type, PROV.Activity) in graph
    assert (reviewer, RDF.type, PROV.Agent) in graph
    assert (log, PROV.wasGeneratedBy, session) in graph
    assert (session, PROV.wasAssociatedWith, reviewer) in graph
    assert next(graph.objects(session, PROV.startedAtTime), None) == Literal(
        decision_log["review_session"]["started_at"], datatype=XSD.dateTime
    )
    assert next(graph.objects(session, PROV.endedAtTime), None) == Literal(
        decision_log["review_session"]["completed_at"], datatype=XSD.dateTime
    )
    assert next(graph.objects(reviewer, DCTERMS.title), None) == Literal(
        decision_log["reviewer"]["display_name"]
    )
    assert next(graph.objects(reviewer, DCTERMS.type), None) == Literal(
        decision_log["reviewer"]["role"]
    )
    for decision in decision_log["decisions"]:
        record = URIRef(decision["decision_id"])
        assert (record, RDF.type, MNP.ReviewDecision) in graph
        assert Literal(decision["decision"]) in graph.objects(record, MNP.reviewOutcomeCode)
        assert Literal(decision["rationale"]) in graph.objects(record, DCTERMS.description)
        assert next(graph.objects(record, DCTERMS.creator), None) is not None
        assert Literal(decision["decided_at"], datatype=XSD.dateTime) in graph.objects(
            record, PROV.generatedAtTime
        )
        if decision.get("evidence_refs"):
            assert next(graph.objects(record, DCTERMS.references), None) is not None


@pytest.mark.parametrize("scenario", ["full-confirmation", "modified-confirmation", "rejection", "issue-resolution"])
def test_review_audit_concept_boundary_and_decision_traceability(tmp_path, scenario):
    directory, _, _ = build(tmp_path, scenario)
    values = authorities(scenario)
    decision_log = values[2]
    graph = Graph()
    graph.parse(directory / "rdf" / "review-audit.nt", format="nt")

    log = URIRef(decision_log["decision_log_id"])
    session = URIRef(decision_log["review_session"]["session_id"])
    reviewer = URIRef(decision_log["reviewer"]["reviewer_id"])
    assert (log, RDF.type, MNP.ReviewDecision) not in graph
    assert (session, RDF.type, MNP.ReviewDecision) not in graph
    assert (reviewer, RDF.type, MNP.ReviewDecision) not in graph
    decisions = [URIRef(item["decision_id"]) for item in decision_log["decisions"]]
    assert len(list(graph.subjects(RDF.type, MNP.ReviewDecision))) == len(decisions)
    assert set(graph.subjects(RDF.type, MNP.ReviewDecision)) == set(decisions)
    assert all(
        next(graph.objects(decision, PROV.generatedAtTime), None)
        == Literal(item["decided_at"], datatype=XSD.dateTime)
        for decision, item in zip(decisions, decision_log["decisions"])
    )
