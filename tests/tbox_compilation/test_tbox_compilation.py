from __future__ import annotations

import pytest
from prompt05_support import candidate
from rdflib import OWL, RDF, RDFS, BNode, Graph, Literal, URIRef

from kg_mnp.semantic_kernel.rdf.canonical import canonical_ntriples
from kg_mnp.semantic_kernel.tbox import compile_tbox


def _identity() -> dict[str, object]:
    return {
        "ontology_iri": "https://example.test/ontology",
        "version_iri": "https://example.test/ontology/1.0.0",
        "ontology_version": "1.0.0",
        "default_namespace": "urn:kg-mnp:project:test:",
        "baseline_ontology_iris": ["https://example.test/baseline"],
    }


def test_tbox_reuse_create_axioms_and_round_trip() -> None:
    baseline = Graph()
    existing = URIRef("https://example.test/baseline#Existing")
    baseline.add((existing, RDF.type, OWL.Class))
    new_class = "urn:kg-mnp:project:test:NewClass"
    new_property = "urn:kg-mnp:project:test:property"
    values = [
        candidate("CLASS", candidate_kind="TBOX", candidate_action="REUSE_EXISTING", target_iri=str(existing)),
        candidate("CLASS", candidate_kind="TBOX", candidate_action="CREATE_NEW", ordinal=1, subject_iri=new_class, label='A "safe" label'),
        candidate("DATA_PROPERTY", candidate_kind="TBOX", candidate_action="CREATE_NEW", ordinal=2, subject_iri=new_property),
        candidate("SUBCLASS_AXIOM", candidate_kind="TBOX", candidate_action="CREATE_NEW", ordinal=3, subject_iri=new_class, object_iri=str(existing)),
        candidate("DOMAIN_AXIOM", candidate_kind="TBOX", candidate_action="CREATE_NEW", ordinal=4, subject_iri=new_property, object_iri=new_class),
        candidate("RANGE_AXIOM", candidate_kind="TBOX", candidate_action="CREATE_NEW", ordinal=5, subject_iri=new_property, object_iri="http://www.w3.org/2001/XMLSchema#string"),
        candidate("DISJOINT_CLASSES_AXIOM", candidate_kind="TBOX", candidate_action="CREATE_NEW", ordinal=6, subject_iri=new_class, object_iri=str(existing)),
    ]
    result = compile_tbox(
        values,
        baseline_graph=baseline,
        ontology_identity=_identity(),
        compiler_snapshot_id="urn:kg-mnp:semantic-compiler-snapshot:" + "1" * 64,
        package_id="urn:kg-mnp:ontology-package:" + "2" * 64,
        plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64,
    )
    assert result.item_triples[values[0]["candidate_id"]] == ()
    assert (URIRef(new_class), RDF.type, OWL.Class) in result.delta
    assert (URIRef(new_class), RDFS.label, Literal('A "safe" label')) in result.delta
    assert (URIRef(new_class), OWL.disjointWith, existing) in result.delta
    assert not any(isinstance(term, BNode) for triple in result.module for term in triple)
    rebuilt = Graph().parse(data=canonical_ntriples(result.module).decode(), format="nt")
    assert canonical_ntriples(rebuilt) == canonical_ntriples(result.module)


def test_tbox_rejects_collision_reserved_namespace_and_wrong_reuse_type() -> None:
    baseline = Graph()
    existing = URIRef("urn:kg-mnp:project:test:Existing")
    baseline.add((existing, RDF.type, OWL.DatatypeProperty))
    with pytest.raises(ValueError, match="collides"):
        compile_tbox(
            [candidate("CLASS", candidate_kind="TBOX", candidate_action="CREATE_NEW", subject_iri=str(existing))],
            baseline_graph=baseline,
            ontology_identity=_identity(),
            compiler_snapshot_id="urn:kg-mnp:semantic-compiler-snapshot:" + "1" * 64,
            package_id="urn:kg-mnp:ontology-package:" + "2" * 64,
            plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64,
        )
    with pytest.raises(ValueError, match="wrong semantic type"):
        compile_tbox(
            [candidate("CLASS", candidate_kind="TBOX", candidate_action="REUSE_EXISTING", target_iri=str(existing))],
            baseline_graph=baseline,
            ontology_identity=_identity(),
            compiler_snapshot_id="urn:kg-mnp:semantic-compiler-snapshot:" + "1" * 64,
            package_id="urn:kg-mnp:ontology-package:" + "2" * 64,
            plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64,
        )

