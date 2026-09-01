"""Deterministic RDF projection of human review authority."""

from __future__ import annotations

from typing import Any

from rdflib import PROV, RDF, Graph, Literal, URIRef

from .namespaces import KGP


def compile_review_audit(
    *,
    confirmed_package: dict[str, Any],
    review_log: dict[str, Any],
    proposal: dict[str, Any],
) -> Graph:
    graph = Graph()
    package = URIRef(confirmed_package["package_id"])
    proposal_ref = URIRef(proposal["proposal_id"])
    log_ref = URIRef(confirmed_package["review_decision_log_id"])
    graph.add((package, RDF.type, KGP.ConfirmedModelingPackage))
    graph.add((package, PROV.wasDerivedFrom, proposal_ref))
    graph.add((package, KGP.reviewDecision, log_ref))
    graph.add((log_ref, KGP.semanticDigest, Literal(confirmed_package["review_semantic_hash"])))
    for action in sorted(review_log.get("actions", review_log.get("decisions", [])), key=lambda item: str(item.get("action_id", item.get("decision_id", "")))):
        action_id = action.get("action_id") or action.get("decision_id")
        candidate_id = action.get("candidate_id")
        if not isinstance(action_id, str):
            continue
        action_ref = URIRef(action_id)
        graph.add((action_ref, RDF.type, KGP.ReviewDecision))
        graph.add((log_ref, PROV.hadMember, action_ref))
        if isinstance(candidate_id, str):
            graph.add((action_ref, KGP.confirmedItem, URIRef(candidate_id)))
        reviewer = action.get("reviewer_id")
        if isinstance(reviewer, str):
            reviewer_ref = URIRef("urn:kg-mnp:reviewer:" + __import__("hashlib").sha256(reviewer.encode()).hexdigest())
            graph.add((action_ref, PROV.wasAssociatedWith, reviewer_ref))
            graph.add((reviewer_ref, KGP.reviewerRole, Literal(str(action.get("reviewer_role", "DECLARED_REVIEWER")))))
    return graph
