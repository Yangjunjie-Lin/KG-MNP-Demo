"""Deterministic evidence-bound ABox compilation."""

from __future__ import annotations

from typing import Any

from rdflib import OWL, RDF, Graph, URIRef

from .contracts import finalize_artifact
from .literals import compile_literal
from .models import CompilationResult
from .rdf.canonical import graph_semantic_digest
from .security import validate_iri


def _typed(graph: Graph, iri: URIRef, rdf_type: URIRef) -> bool:
    return (iri, RDF.type, rdf_type) in graph


def _known_individual(graph: Graph, iri: URIRef, compiled: set[URIRef]) -> bool:
    return iri in compiled or _typed(graph, iri, OWL.NamedIndividual)


def compile_abox(
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    effective_tbox: Graph,
    plan_id: str,
) -> CompilationResult:
    graph = Graph()
    item_triples: dict[str, tuple[tuple[Any, Any, Any], ...]] = {}
    rows = []
    ordered = sorted(candidates, key=lambda item: (item["body"]["candidate_type"] != "INDIVIDUAL", item["candidate_id"]))
    known_individuals: set[URIRef] = set()
    functional_values: dict[tuple[URIRef, URIRef], object] = {}
    for candidate in ordered:
        body = candidate["body"]
        kind = body["candidate_type"]
        subject_value = body.get("subject_iri")
        if not isinstance(subject_value, str):
            raise TypeError(f"{kind} lacks subject_iri")
        subject = URIRef(validate_iri(subject_value))
        triples = []
        if kind == "INDIVIDUAL":
            triple = (subject, RDF.type, OWL.NamedIndividual)
            known_individuals.add(subject)
        elif kind == "CLASS_ASSERTION":
            obj_value = body.get("object_iri")
            if not _known_individual(effective_tbox, subject, known_individuals) or not isinstance(obj_value, str):
                raise ValueError("class assertion refers to a missing subject or class")
            obj = URIRef(validate_iri(obj_value))
            if not _typed(effective_tbox, obj, OWL.Class):
                raise ValueError("class assertion object is not a known class")
            triple = (subject, RDF.type, obj)
        elif kind == "DATA_PROPERTY_ASSERTION":
            predicate_value = body.get("predicate_iri")
            if not _known_individual(effective_tbox, subject, known_individuals) or not isinstance(predicate_value, str):
                raise ValueError("data assertion refers to a missing subject or property")
            predicate = URIRef(validate_iri(predicate_value))
            if not _typed(effective_tbox, predicate, OWL.DatatypeProperty):
                raise ValueError("data assertion predicate is not a known data property")
            if not isinstance(body.get("literal"), dict):
                raise ValueError("data assertion lacks a literal")
            obj = compile_literal(body["literal"])
            triple = (subject, predicate, obj)
            if _typed(effective_tbox, predicate, OWL.FunctionalProperty):
                key = (subject, predicate)
                if key in functional_values and functional_values[key] != obj:
                    raise ValueError("functional data property has conflicting values")
                functional_values[key] = obj
        elif kind == "OBJECT_PROPERTY_ASSERTION":
            predicate_value = body.get("predicate_iri")
            obj_value = body.get("object_iri")
            if not _known_individual(effective_tbox, subject, known_individuals) or not isinstance(predicate_value, str) or not isinstance(obj_value, str):
                raise ValueError("object assertion refers to a missing subject, property, or object")
            predicate = URIRef(validate_iri(predicate_value))
            obj = URIRef(validate_iri(obj_value))
            if not _typed(effective_tbox, predicate, OWL.ObjectProperty):
                raise ValueError("object assertion predicate is not a known object property")
            if not _known_individual(effective_tbox, obj, known_individuals):
                raise ValueError("object assertion target is not a known individual")
            triple = (subject, predicate, obj)
        else:
            raise ValueError(f"unsupported ABox candidate: {kind}")
        if triple in graph:
            raise ValueError("duplicate confirmed ABox statement")
        graph.add(triple)
        triples.append(triple)
        item_triples[candidate["candidate_id"]] = tuple(triples)
        rows.append({"confirmed_item_id": candidate["candidate_id"], "candidate_type": kind, "output_ids": [], "statement_count": 1})
    core = {"manifest_kind": "KG_MNP_ABOX_COMPILATION_REPORT", "schema_version": "1.0.0", "plan_id": plan_id, "partition": "ABOX", "items": rows, "statement_count": len(graph), "semantic_sha256": graph_semantic_digest(graph), "output_files": ["data/abox.nt", "data/abox.ttl"], "status": "PASSED", "issues": []}
    report = finalize_artifact(core, id_field="report_id", urn_kind="abox-compilation-report", contract="abox-compilation-report")
    return CompilationResult(graph=graph, report=report, item_triples=item_triples)
