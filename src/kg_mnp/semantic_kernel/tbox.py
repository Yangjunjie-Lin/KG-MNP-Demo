"""Deterministic overlay TBox compilation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rdflib import OWL, RDF, RDFS, Graph, Literal, URIRef

from .contracts import finalize_artifact
from .namespaces import KGP
from .rdf.canonical import graph_semantic_digest
from .security import validate_iri


@dataclass(frozen=True)
class TBoxResult:
    module: Graph
    delta: Graph
    effective: Graph
    report: dict[str, Any]
    item_triples: dict[str, tuple[tuple[Any, Any, Any], ...]]


def _candidate_iri(body: dict[str, Any]) -> str:
    value = body.get("subject_iri") or body.get("target_iri")
    if not isinstance(value, str):
        raise TypeError("TBox candidate lacks its subject or target IRI")
    return validate_iri(value)


def _exists(graph: Graph, iri: URIRef) -> bool:
    return any(graph.triples((iri, None, None))) or any(graph.triples((None, None, iri)))


def compile_tbox(
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    baseline_graph: Graph,
    ontology_identity: dict[str, Any],
    compiler_snapshot_id: str,
    package_id: str,
    plan_id: str,
) -> TBoxResult:
    delta = Graph()
    item_triples: dict[str, tuple[tuple[Any, Any, Any], ...]] = {}
    rows = []
    allowed_namespace = ontology_identity["default_namespace"]
    for candidate in sorted(candidates, key=lambda item: item["candidate_id"]):
        body = candidate["body"]
        kind = body["candidate_type"]
        action = candidate["candidate_action"]
        target = URIRef(_candidate_iri(body))
        if action in {"REUSE_EXISTING", "ALIGN_TO_EXISTING"}:
            if not _exists(baseline_graph, target):
                raise ValueError("TBox reuse/alignment target does not exist in the locked baseline")
            required_type = {
                "CLASS": OWL.Class,
                "OBJECT_PROPERTY": OWL.ObjectProperty,
                "DATA_PROPERTY": OWL.DatatypeProperty,
            }.get(kind)
            if required_type is not None and (target, RDF.type, required_type) not in baseline_graph:
                raise ValueError("TBox reuse/alignment target has the wrong semantic type")
            triples: list[tuple[Any, Any, Any]] = []
        else:
            if not str(target).startswith(allowed_namespace):
                raise ValueError("new TBox IRI is outside the approved namespace")
            if _exists(baseline_graph, target):
                raise ValueError("new TBox IRI collides with the locked baseline")
            triples = []
            if kind == "CLASS":
                triples.append((target, RDF.type, OWL.Class))
            elif kind == "OBJECT_PROPERTY":
                triples.append((target, RDF.type, OWL.ObjectProperty))
            elif kind == "DATA_PROPERTY":
                triples.append((target, RDF.type, OWL.DatatypeProperty))
            elif kind in {"SUBCLASS_AXIOM", "DOMAIN_AXIOM", "RANGE_AXIOM", "DISJOINT_CLASSES_AXIOM"}:
                obj_value = body.get("object_iri")
                if not isinstance(obj_value, str):
                    raise ValueError(f"{kind} lacks object_iri")
                obj = URIRef(validate_iri(obj_value))
                predicate = {
                    "SUBCLASS_AXIOM": RDFS.subClassOf,
                    "DOMAIN_AXIOM": RDFS.domain,
                    "RANGE_AXIOM": RDFS.range,
                    "DISJOINT_CLASSES_AXIOM": OWL.disjointWith,
                }[kind]
                triples.append((target, predicate, obj))
            else:
                raise ValueError(f"unsupported TBox candidate: {kind}")
            if body.get("label") and kind in {"CLASS", "OBJECT_PROPERTY", "DATA_PROPERTY"}:
                triples.append((target, RDFS.label, Literal(body["label"])))
            for triple in triples:
                delta.add(triple)
        item_triples[candidate["candidate_id"]] = tuple(sorted(triples, key=lambda triple: tuple(term.n3() for term in triple)))
        rows.append({"confirmed_item_id": candidate["candidate_id"], "candidate_type": kind, "output_ids": [], "statement_count": len(triples)})

    ontology = URIRef(validate_iri(ontology_identity["ontology_iri"]))
    version_iri = URIRef(validate_iri(ontology_identity["version_iri"]))
    module = Graph()
    module.add((ontology, RDF.type, OWL.Ontology))
    module.add((ontology, OWL.versionIRI, version_iri))
    module.add((ontology, OWL.versionInfo, Literal(ontology_identity["ontology_version"])))
    module.add((ontology, KGP.compilerSnapshot, URIRef(compiler_snapshot_id)))
    module.add((ontology, KGP.ontologyPackage, URIRef(package_id)))
    for baseline_iri in sorted(ontology_identity.get("baseline_ontology_iris", [])):
        module.add((ontology, OWL.imports, URIRef(validate_iri(baseline_iri))))
    for triple in delta:
        module.add(triple)
    effective = Graph()
    for graph in (baseline_graph, delta):
        for triple in graph:
            if triple[1] != OWL.imports:
                effective.add(triple)
    for subject, predicate, obj in delta:
        if predicate in {RDFS.subClassOf, OWL.disjointWith}:
            if (subject, RDF.type, OWL.Class) not in effective or (obj, RDF.type, OWL.Class) not in effective:
                raise ValueError("class axiom refers to an unknown or non-class IRI")
        elif predicate in {RDFS.domain, RDFS.range}:
            property_types = {OWL.ObjectProperty, OWL.DatatypeProperty}
            if not any((subject, RDF.type, value) in effective for value in property_types):
                raise ValueError("domain/range axiom subject is not a known property")
            if predicate == RDFS.domain and (obj, RDF.type, OWL.Class) not in effective:
                raise ValueError("domain axiom object is not a known class")
            if predicate == RDFS.range and (subject, RDF.type, OWL.ObjectProperty) in effective and (obj, RDF.type, OWL.Class) not in effective:
                raise ValueError("object-property range is not a known class")
    digest = graph_semantic_digest(delta)
    core = {"manifest_kind": "KG_MNP_TBOX_COMPILATION_REPORT", "schema_version": "1.0.0", "plan_id": plan_id, "partition": "TBOX", "items": rows, "statement_count": len(delta), "semantic_sha256": digest, "output_files": ["ontology/module.nt", "ontology/module.ttl", "ontology/tbox-delta.nt", "ontology/tbox-delta.ttl", "ontology/effective-tbox.nt", "ontology/effective-tbox.ttl", "ontology/import-catalog.xml"], "status": "PASSED", "issues": []}
    report = finalize_artifact(core, id_field="report_id", urn_kind="tbox-compilation-report", contract="tbox-compilation-report")
    return TBoxResult(module=module, delta=delta, effective=effective, report=report, item_triples=item_triples)
