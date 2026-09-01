from __future__ import annotations

import time

from rdflib import RDF, SH, XSD, Graph, Literal, URIRef

from kg_mnp.semantic_kernel.validators import shacl as shacl_validator
from kg_mnp.semantic_kernel.validators.shacl import validate_shacl


def _sleeping_shacl_worker(*_args) -> None:
    time.sleep(30)


def _failed_shacl_worker(_data, _shapes, _ontology, output) -> None:
    output.put(("ENGINE_ERROR", False, ["ControlledFailure"]))


def _shapes() -> Graph:
    graph = Graph()
    shape = URIRef("urn:test:shape")
    property_shape = URIRef("urn:test:shape-property")
    graph.add((shape, RDF.type, SH.NodeShape))
    graph.add((shape, SH.targetClass, URIRef("urn:test:Class")))
    graph.add((shape, SH.property, property_shape))
    graph.add((property_shape, RDF.type, SH.PropertyShape))
    graph.add((property_shape, SH.path, URIRef("urn:test:name")))
    graph.add((property_shape, SH.minCount, Literal(1)))
    graph.add((property_shape, SH.datatype, XSD.string))
    return graph


def test_final_shacl_conforms_and_has_deterministic_report() -> None:
    data = Graph()
    data.add((URIRef("urn:test:entity"), RDF.type, URIRef("urn:test:Class")))
    data.add((URIRef("urn:test:entity"), URIRef("urn:test:name"), Literal("Entity")))
    first, first_graph = validate_shacl(data_graph=data, shapes_graph=_shapes(), ontology_graph=Graph(), max_seconds=30)
    second, second_graph = validate_shacl(data_graph=data, shapes_graph=_shapes(), ontology_graph=Graph(), max_seconds=30)
    assert first == second
    assert set(first_graph) == set(second_graph)
    assert first["status"] == "CONFORMS" and first["meta_shacl_status"] == "PASSED"


def test_final_shacl_violation_fails_gate() -> None:
    data = Graph()
    data.add((URIRef("urn:test:entity"), RDF.type, URIRef("urn:test:Class")))
    report, _ = validate_shacl(data_graph=data, shapes_graph=_shapes(), ontology_graph=Graph(), max_seconds=30)
    assert report["status"] == "VIOLATION"
    assert report["violation_count"] == 1 and report["conforms"] is False


def test_final_shacl_timeout_terminates_child_and_fails_gate(monkeypatch) -> None:
    monkeypatch.setattr(shacl_validator, "_shacl_worker", _sleeping_shacl_worker)
    started = time.monotonic()
    report, graph = validate_shacl(
        data_graph=Graph(),
        shapes_graph=Graph(),
        ontology_graph=Graph(),
        max_seconds=1,
    )
    assert time.monotonic() - started < 10
    assert report["status"] == "TIMEOUT"
    assert report["conforms"] is False
    assert len(graph) == 0


def test_final_shacl_engine_error_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(shacl_validator, "_shacl_worker", _failed_shacl_worker)
    report, graph = validate_shacl(
        data_graph=Graph(),
        shapes_graph=Graph(),
        ontology_graph=Graph(),
        max_seconds=10,
    )
    assert report["status"] == "ENGINE_ERROR"
    assert report["meta_shacl_status"] == "NOT_RUN_UNSUPPORTED"
    assert len(graph) == 0
