"""Deterministic SHACL Core compilation with skolemized RDF lists."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rdflib import OWL, RDF, SH, Graph, Literal, URIRef

from .contracts import finalize_artifact
from .identifiers import skolem_iri
from .rdf.canonical import graph_semantic_digest
from .security import validate_iri

_PROHIBITED_SHACL_TYPES = {
    SH.JSConstraint,
    SH.JSFunction,
    SH.SPARQLConstraint,
    SH.SPARQLFunction,
}
_PROHIBITED_SHACL_PREDICATES = {
    SH.ask,
    SH.construct,
    SH.js,
    SH.select,
    SH.sparql,
    SH.update,
}


def project_safe_baseline_shapes(graph: Graph) -> tuple[Graph, int]:
    """Project a locked legacy graph to inert SHACL Core without executing code.

    Prompt 5 confirmed shapes are never projected: they must already be safe.
    A legacy baseline can contain historical SPARQL/JS validator structures; the
    immutable source bytes remain packaged, while each connected executable
    shape component is deterministically excluded from the effective graph.
    """

    unsafe = {
        subject
        for subject, predicate, obj in graph
        if predicate in _PROHIBITED_SHACL_PREDICATES
        or (predicate == RDF.type and obj in _PROHIBITED_SHACL_TYPES)
    }
    changed = True
    while changed:
        changed = False
        for subject, _, obj in graph:
            if obj in unsafe and subject not in unsafe:
                unsafe.add(subject)
                changed = True
            if (
                subject in unsafe
                and isinstance(obj, URIRef)
                and str(obj).startswith("urn:kg-mnp:baseline-skolem:")
                and obj not in unsafe
            ):
                unsafe.add(obj)
                changed = True
    projected = Graph()
    for triple in graph:
        if triple[0] not in unsafe and triple[2] not in unsafe:
            projected.add(triple)
    return projected, len(graph) - len(projected)


def assert_safe_shacl_graph(graph: Graph) -> None:
    if any(graph.triples((None, OWL.imports, None))):
        raise ValueError("SHACL remote/import closure is prohibited")
    if any(predicate in _PROHIBITED_SHACL_PREDICATES for _, predicate, _ in graph):
        raise ValueError("SHACL-SPARQL, JavaScript, and custom executable constraints are prohibited")
    if any(value in _PROHIBITED_SHACL_TYPES for value in graph.objects(None, RDF.type)):
        raise ValueError("SHACL executable constraint/function types are prohibited")


@dataclass(frozen=True)
class SHACLResult:
    compiled: Graph
    effective: Graph
    report: dict[str, Any]
    item_triples: dict[str, tuple[tuple[Any, Any, Any], ...]]


def _shape_iri(candidate: dict[str, Any]) -> URIRef:
    body = candidate["body"]
    value = body.get("subject_iri") or body.get("target_iri")
    if isinstance(value, str):
        return URIRef(validate_iri(value, label="shape IRI"))
    return URIRef(skolem_iri("shape", {"candidate_id": candidate["candidate_id"]}))


def compile_shacl(
    candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    baseline_shapes: Graph,
    plan_id: str,
) -> SHACLResult:
    graph = Graph()
    item_triples: dict[str, tuple[tuple[Any, Any, Any], ...]] = {}
    rows = []
    cardinalities: dict[tuple[str, str], dict[str, int]] = {}
    for candidate in sorted(candidates, key=lambda item: item["candidate_id"]):
        body = candidate["body"]
        kind = body["candidate_type"]
        shape = _shape_iri(candidate)
        triples: list[tuple[Any, Any, Any]] = []
        if kind == "NODE_SHAPE":
            triples.append((shape, RDF.type, SH.NodeShape))
            target = body.get("target_iri") or body.get("object_iri")
            if isinstance(target, str) and target != str(shape):
                triples.append((shape, SH.targetClass, URIRef(validate_iri(target))))
        elif kind == "PROPERTY_SHAPE":
            triples.append((shape, RDF.type, SH.PropertyShape))
            path = body.get("predicate_iri") or body.get("object_iri")
            if not isinstance(path, str):
                raise ValueError("property shape requires a direct IRI path")
            triples.append((shape, SH.path, URIRef(validate_iri(path))))
        else:
            path = body.get("predicate_iri")
            if isinstance(path, str):
                triples.append((shape, SH.path, URIRef(validate_iri(path))))
            if kind in {"MIN_COUNT", "MAX_COUNT"}:
                value = body.get("integer_value")
                if not isinstance(value, int) or value < 0:
                    raise ValueError("SHACL cardinality must be a non-negative integer")
                predicate = SH.minCount if kind == "MIN_COUNT" else SH.maxCount
                triples.append((shape, predicate, Literal(value)))
                key = (str(shape), str(path))
                cardinalities.setdefault(key, {})[kind] = value
            elif kind == "DATATYPE":
                target = body.get("object_iri") or body.get("target_iri")
                if not isinstance(target, str):
                    raise ValueError("SHACL datatype constraint lacks datatype IRI")
                triples.append((shape, SH.datatype, URIRef(validate_iri(target))))
            elif kind == "CLASS_CONSTRAINT":
                target = body.get("object_iri") or body.get("target_iri")
                if not isinstance(target, str):
                    raise ValueError("SHACL class constraint lacks class IRI")
                triples.append((shape, SH["class"], URIRef(validate_iri(target))))
            elif kind == "NODE_KIND":
                target = body.get("object_iri") or body.get("target_iri")
                if not isinstance(target, str) or target not in {str(SH.IRI), str(SH.Literal), str(SH.BlankNode), str(SH.BlankNodeOrIRI), str(SH.BlankNodeOrLiteral), str(SH.IRIOrLiteral)}:
                    raise ValueError("unsupported SHACL node kind")
                triples.append((shape, SH.nodeKind, URIRef(target)))
            elif kind == "IN_VALUES":
                values = [Literal(value, normalize=False) for value in body.get("values", [])]
                if not values:
                    raise ValueError("SHACL in-values constraint must be non-empty")
                nodes = [URIRef(skolem_iri("shacl-list", {"candidate_id": candidate["candidate_id"], "index": index, "values": body["values"]})) for index in range(len(values))]
                triples.append((shape, SH["in"], nodes[0]))
                for index, (node, value) in enumerate(zip(nodes, values, strict=True)):
                    triples.append((node, RDF.first, value))
                    triples.append((node, RDF.rest, RDF.nil if index == len(nodes) - 1 else nodes[index + 1]))
            else:
                raise ValueError(f"unsupported SHACL candidate: {kind}")
        for triple in triples:
            graph.add(triple)
        item_triples[candidate["candidate_id"]] = tuple(sorted(triples, key=lambda triple: tuple(term.n3() for term in triple)))
        rows.append({"confirmed_item_id": candidate["candidate_id"], "candidate_type": kind, "output_ids": [str(shape)], "statement_count": len(triples)})
    for values in cardinalities.values():
        if "MIN_COUNT" in values and "MAX_COUNT" in values and values["MIN_COUNT"] > values["MAX_COUNT"]:
            raise ValueError("SHACL minCount exceeds maxCount")
    assert_safe_shacl_graph(graph)
    safe_baseline, excluded_baseline_statements = project_safe_baseline_shapes(
        baseline_shapes
    )
    effective = Graph()
    for source in (safe_baseline, graph):
        for triple in source:
            effective.add(triple)
    assert_safe_shacl_graph(effective)
    core = {"manifest_kind": "KG_MNP_SHACL_COMPILATION_REPORT", "schema_version": "1.0.0", "plan_id": plan_id, "partition": "SHACL", "items": rows, "statement_count": len(graph), "baseline_statement_count": len(baseline_shapes), "effective_statement_count": len(effective), "excluded_baseline_statement_count": excluded_baseline_statements, "baseline_projection": "SAFE_SHACL_CORE_PROJECTION", "semantic_sha256": graph_semantic_digest(graph), "output_files": ["shapes/compiled-shapes.nt", "shapes/compiled-shapes.ttl", "shapes/effective-shapes.nt", "shapes/effective-shapes.ttl"], "status": "PASSED", "issues": []}
    report = finalize_artifact(core, id_field="report_id", urn_kind="shacl-compilation-report", contract="shacl-compilation-report")
    return SHACLResult(compiled=graph, effective=effective, report=report, item_triples=item_triples)
