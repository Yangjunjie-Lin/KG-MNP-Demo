from __future__ import annotations

import pytest
from prompt05_support import candidate
from rdflib import OWL, RDF, XSD, BNode, Graph, Literal, URIRef

from kg_mnp.semantic_kernel.abox import compile_abox
from kg_mnp.semantic_kernel.rdf.canonical import canonical_ntriples


def _tbox() -> Graph:
    graph = Graph()
    for iri, rdf_type in (
        ("urn:test:Class", OWL.Class),
        ("urn:test:name", OWL.DatatypeProperty),
        ("urn:test:knows", OWL.ObjectProperty),
    ):
        graph.add((URIRef(iri), RDF.type, rdf_type))
    graph.add((URIRef("urn:test:name"), RDF.type, OWL.FunctionalProperty))
    return graph


def test_abox_compiles_all_assertion_kinds_and_escapes_literals() -> None:
    left = "urn:test:left"
    right = "urn:test:right"
    values = [
        candidate("INDIVIDUAL", candidate_kind="ABOX", candidate_action="ASSERT", subject_iri=left),
        candidate("INDIVIDUAL", candidate_kind="ABOX", candidate_action="ASSERT", ordinal=1, subject_iri=right),
        candidate("CLASS_ASSERTION", candidate_kind="ABOX", candidate_action="ASSERT", ordinal=2, subject_iri=left, object_iri="urn:test:Class"),
        candidate("DATA_PROPERTY_ASSERTION", candidate_kind="ABOX", candidate_action="ASSERT", ordinal=3, subject_iri=left, predicate_iri="urn:test:name", literal={"lexical_value": 'quoted "value"', "datatype_iri": str(XSD.string), "language": None}),
        candidate("OBJECT_PROPERTY_ASSERTION", candidate_kind="ABOX", candidate_action="ASSERT", ordinal=4, subject_iri=left, predicate_iri="urn:test:knows", object_iri=right),
    ]
    result = compile_abox(values, effective_tbox=_tbox(), plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64)
    assert (URIRef(left), URIRef("urn:test:name"), Literal('quoted "value"', datatype=XSD.string)) in result.graph
    assert len(result.graph) == 5
    assert not any(isinstance(term, BNode) for triple in result.graph for term in triple)
    rebuilt = Graph().parse(data=canonical_ntriples(result.graph).decode(), format="nt")
    assert canonical_ntriples(rebuilt) == canonical_ntriples(result.graph)


@pytest.mark.parametrize(
    ("literal", "message"),
    [
        ({"lexical_value": "not-an-int", "datatype_iri": str(XSD.integer), "language": None}, "lexical"),
        ({"lexical_value": "value", "datatype_iri": None, "language": "bad_tag!"}, "language"),
        ({"lexical_value": "value", "datatype_iri": str(XSD.string), "language": "en"}, "cannot combine"),
    ],
)
def test_abox_rejects_invalid_literals(literal: dict[str, object], message: str) -> None:
    values = [
        candidate("INDIVIDUAL", candidate_kind="ABOX", candidate_action="ASSERT", subject_iri="urn:test:left"),
        candidate("DATA_PROPERTY_ASSERTION", candidate_kind="ABOX", candidate_action="ASSERT", ordinal=1, subject_iri="urn:test:left", predicate_iri="urn:test:name", literal=literal),
    ]
    with pytest.raises(ValueError, match=message):
        compile_abox(values, effective_tbox=_tbox(), plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64)


def test_abox_rejects_property_type_confusion_and_functional_conflict() -> None:
    values = [
        candidate("INDIVIDUAL", candidate_kind="ABOX", candidate_action="ASSERT", subject_iri="urn:test:left"),
        candidate("DATA_PROPERTY_ASSERTION", candidate_kind="ABOX", candidate_action="ASSERT", ordinal=1, subject_iri="urn:test:left", predicate_iri="urn:test:name", literal={"lexical_value": "one", "datatype_iri": None, "language": "en"}),
        candidate("DATA_PROPERTY_ASSERTION", candidate_kind="ABOX", candidate_action="ASSERT", ordinal=2, subject_iri="urn:test:left", predicate_iri="urn:test:name", literal={"lexical_value": "two", "datatype_iri": None, "language": "en"}),
    ]
    with pytest.raises(ValueError, match="functional"):
        compile_abox(values, effective_tbox=_tbox(), plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64)
    wrong = [
        values[0],
        candidate("DATA_PROPERTY_ASSERTION", candidate_kind="ABOX", candidate_action="ASSERT", ordinal=4, subject_iri="urn:test:left", predicate_iri="urn:test:knows", literal={"lexical_value": "x", "datatype_iri": None, "language": None}),
    ]
    with pytest.raises(ValueError, match="not a known data property"):
        compile_abox(wrong, effective_tbox=_tbox(), plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64)

