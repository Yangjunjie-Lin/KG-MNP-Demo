from __future__ import annotations

import pytest
from prompt05_support import candidate
from rdflib import OWL, RDF, SH, BNode, Graph, URIRef

from kg_mnp.semantic_kernel.rdf.canonical import canonical_ntriples
from kg_mnp.semantic_kernel.shacl import (
    assert_safe_shacl_graph,
    compile_shacl,
    project_safe_baseline_shapes,
)


def test_shacl_core_compilation_is_skolemized_and_deterministic() -> None:
    shape = "urn:test:shape"
    values = [
        candidate("PROPERTY_SHAPE", candidate_kind="SHACL", candidate_action="CONSTRAIN", subject_iri=shape, predicate_iri="urn:test:name"),
        candidate("MIN_COUNT", candidate_kind="SHACL", candidate_action="CONSTRAIN", ordinal=1, subject_iri=shape, predicate_iri="urn:test:name", integer_value=1),
        candidate("MAX_COUNT", candidate_kind="SHACL", candidate_action="CONSTRAIN", ordinal=2, subject_iri=shape, predicate_iri="urn:test:name", integer_value=2),
        candidate("IN_VALUES", candidate_kind="SHACL", candidate_action="CONSTRAIN", ordinal=3, subject_iri=shape, predicate_iri="urn:test:name", values=["alpha", "beta"]),
    ]
    result = compile_shacl(values, baseline_shapes=Graph(), plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64)
    repeated = compile_shacl(list(reversed(values)), baseline_shapes=Graph(), plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64)
    assert canonical_ntriples(result.compiled) == canonical_ntriples(repeated.compiled)
    assert (URIRef(shape), SH.minCount, None) in result.compiled
    assert not any(isinstance(term, BNode) for triple in result.effective for term in triple)


def test_shacl_rejects_invalid_cardinality_and_executable_features() -> None:
    values = [
        candidate("MIN_COUNT", candidate_kind="SHACL", candidate_action="CONSTRAIN", subject_iri="urn:test:shape", predicate_iri="urn:test:name", integer_value=2),
        candidate("MAX_COUNT", candidate_kind="SHACL", candidate_action="CONSTRAIN", ordinal=1, subject_iri="urn:test:shape", predicate_iri="urn:test:name", integer_value=1),
    ]
    with pytest.raises(ValueError, match="minCount"):
        compile_shacl(values, baseline_shapes=Graph(), plan_id="urn:kg-mnp:semantic-compilation-plan:" + "3" * 64)
    for predicate, value in ((SH.select, "SELECT * WHERE {}"), (SH.js, "alert(1)")):
        graph = Graph()
        graph.add((URIRef("urn:test:shape"), predicate, URIRef("urn:test:value") if predicate == SH.js else URIRef("urn:test:query")))
        with pytest.raises(ValueError, match="prohibited"):
            assert_safe_shacl_graph(graph)
    imported = Graph()
    imported.add((URIRef("urn:test:shape"), OWL.imports, URIRef("https://example.test/remote")))
    with pytest.raises(ValueError, match="import"):
        assert_safe_shacl_graph(imported)


def test_legacy_baseline_executable_shape_is_projected_without_mutating_source() -> None:
    baseline = Graph()
    shape = URIRef("urn:test:legacy-shape")
    constraint = URIRef("urn:kg-mnp:baseline-skolem:" + "a" * 64)
    baseline.add((shape, RDF.type, SH.NodeShape))
    baseline.add((shape, SH.sparql, constraint))
    baseline.add((constraint, RDF.type, SH.SPARQLConstraint))
    baseline.add((constraint, SH.select, URIRef("urn:test:query")))
    before = set(baseline)
    projected, excluded = project_safe_baseline_shapes(baseline)
    assert excluded == len(baseline)
    assert len(projected) == 0
    assert set(baseline) == before
