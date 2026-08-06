"""Deterministic human-review audit graph."""

from __future__ import annotations

from typing import Any, Mapping

from rdflib import DCTERMS, RDF, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV

from ..modeling.canonical_json import semantic_hash
from .identifiers import review_record_id

MNP = Namespace("https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#")


def _resource(value: str) -> URIRef | Literal:
    return URIRef(value) if value.startswith(("http://", "https://", "urn:")) else Literal(value)


def _date_time(value: str) -> Literal:
    return Literal(value, datatype=XSD.dateTime, normalize=False)


def compile_review_audit(
    decision_log: Mapping[str, Any],
    package: Mapping[str, Any],
) -> Graph:
    graph = Graph()
    log = URIRef(str(decision_log["decision_log_id"]))
    session = decision_log.get("review_session", {})
    reviewer = decision_log.get("reviewer", {})
    graph.add((log, RDF.type, PROV.Entity))
    graph.add((log, DCTERMS.identifier, Literal(str(decision_log["decision_log_id"]))))
    session_id = str(session.get("session_id", ""))
    session_iri = URIRef(session_id)
    graph.add((log, PROV.wasGeneratedBy, session_iri))
    graph.add((session_iri, RDF.type, PROV.Activity))
    if session.get("started_at"):
        graph.add((session_iri, PROV.startedAtTime, _date_time(str(session["started_at"]))))
    if session.get("completed_at"):
        graph.add((session_iri, PROV.endedAtTime, _date_time(str(session["completed_at"]))))
    reviewer_id = str(reviewer.get("reviewer_id", ""))
    if reviewer_id:
        reviewer_iri = URIRef(reviewer_id)
        graph.add((reviewer_iri, RDF.type, PROV.Agent))
        graph.add((session_iri, PROV.wasAssociatedWith, reviewer_iri))
        graph.add((reviewer_iri, DCTERMS.identifier, Literal(reviewer_id)))
        if reviewer.get("display_name"):
            graph.add((reviewer_iri, DCTERMS.title, Literal(str(reviewer["display_name"]))))
        if reviewer.get("role"):
            graph.add((reviewer_iri, DCTERMS.type, Literal(str(reviewer["role"]))))
        if reviewer.get("affiliation"):
            graph.add((reviewer_iri, DCTERMS.description, Literal(str(reviewer["affiliation"]))))

    package_items: dict[str, Mapping[str, Any]] = {}
    for field in ("confirmed_abox_decisions", "rejected_items", "deferred_items"):
        for item in package.get(field, []):
            package_items[str(item.get("decision_id"))] = item

    for decision in sorted(decision_log.get("decisions", []), key=lambda item: str(item.get("decision_id"))):
        decision_iri = URIRef(str(decision["decision_id"]))
        graph.add((decision_iri, RDF.type, MNP.ReviewDecision))
        graph.add((decision_iri, MNP.reviewOutcomeCode, Literal(str(decision["decision"]))))
        graph.add((decision_iri, DCTERMS.description, Literal(str(decision["rationale"]))))
        graph.add((decision_iri, DCTERMS.creator, _resource(str(decision["reviewer_id"]))))
        graph.add((decision_iri, PROV.generatedAtTime, _date_time(str(decision["decided_at"]))))
        graph.add((log, DCTERMS.hasPart, decision_iri))
        target = decision.get("candidate_id") or decision.get("issue_id")
        if isinstance(target, str):
            graph.add((decision_iri, DCTERMS.subject, URIRef(target)))
        for evidence_ref in sorted(decision.get("evidence_refs", [])):
            evidence = URIRef("urn:kg-mnp:review-evidence:" + semantic_hash(str(evidence_ref)))
            graph.add((evidence, DCTERMS.identifier, Literal(str(evidence_ref))))
            graph.add((decision_iri, DCTERMS.references, evidence))
        package_item = package_items.get(str(decision["decision_id"]))
        if package_item is not None:
            record = URIRef(review_record_id(dict(package_item)))
            graph.add((record, DCTERMS.source, decision_iri))
            graph.add((record, DCTERMS.subject, URIRef(str(target))))
            graph.add((record, DCTERMS.type, Literal(str(decision["decision"]))))
    return graph
