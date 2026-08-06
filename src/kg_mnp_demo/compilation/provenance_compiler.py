"""Axiom-level modeling provenance, separated from business facts."""

from __future__ import annotations

from typing import Mapping, Sequence

from rdflib import DCTERMS, OWL, RDF, Graph, Literal, Namespace, URIRef

from ..modeling.canonical_json import canonical_json_bytes
from .abox_compiler import CompiledAssertion
from .identifiers import (
    compiled_assertion_id,
    mapping_rule_id,
    modeling_evidence_id,
    source_field_id,
    source_record_id,
)

MNP = Namespace("https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#")


def compile_modeling_provenance(assertions: Sequence[CompiledAssertion]) -> Graph:
    graph = Graph()
    for assertion in assertions:
        subject, predicate, obj = assertion.triple
        record_payload = {
            "confirmed_item_id": assertion.confirmed_item_id,
            "source_candidate_id": assertion.source_candidate_id,
            "effective_candidate_id": assertion.effective_candidate_id,
            "triple": [subject.n3(), predicate.n3(), obj.n3()],
        }
        record = URIRef(compiled_assertion_id(record_payload))
        decision = URIRef(assertion.decision_id)
        graph.add((record, RDF.type, OWL.Axiom))
        graph.add((record, RDF.type, MNP.ModelingAssertion))
        if assertion.candidate_kind == "OBJECT_PROPERTY_ASSERTION":
            graph.add((record, RDF.type, MNP.RelationAssertion))
        graph.add((record, OWL.annotatedSource, subject))
        graph.add((record, OWL.annotatedProperty, predicate))
        graph.add((record, OWL.annotatedTarget, obj))
        graph.add((record, MNP.hasReviewDecision, decision))
        graph.add((record, DCTERMS.identifier, Literal(assertion.confirmed_item_id)))
        graph.add((record, DCTERMS.source, URIRef(assertion.source_candidate_id)))
        graph.add((record, DCTERMS.relation, URIRef(assertion.effective_candidate_id)))

        content = assertion.semantic_content
        for reference in sorted(content.get("business_fact_evidence_refs", [])):
            source = URIRef(source_record_id(str(reference)))
            graph.add((source, RDF.type, MNP.SourceRecord))
            graph.add((source, DCTERMS.identifier, Literal(str(reference))))
            graph.add((record, DCTERMS.source, source))
        for path in sorted(content.get("source_paths", [])):
            field = URIRef(source_field_id(str(path)))
            graph.add((field, RDF.type, MNP.SourceField))
            graph.add((field, MNP.sourceFieldPath, Literal(str(path))))
            graph.add((record, MNP.mapsSourceField, field))
        for rule_ref in sorted(content.get("mapping_rule_ids", [])):
            rule = URIRef(mapping_rule_id(str(rule_ref)))
            graph.add((rule, RDF.type, MNP.MappingRule))
            graph.add((rule, DCTERMS.identifier, Literal(str(rule_ref))))
            graph.add((record, MNP.usesMappingRule, rule))
        for evidence_ref in sorted(content.get("modeling_evidence_refs", [])):
            evidence = URIRef(modeling_evidence_id(str(evidence_ref)))
            graph.add((evidence, RDF.type, MNP.ModelingEvidence))
            graph.add((evidence, DCTERMS.identifier, Literal(str(evidence_ref))))
            graph.add((record, MNP.hasModelingEvidence, evidence))
        confidence = content.get("confidence")
        if isinstance(confidence, Mapping):
            graph.add((record, DCTERMS.description, Literal(canonical_json_bytes(confidence).decode("utf-8"))))
    return graph
