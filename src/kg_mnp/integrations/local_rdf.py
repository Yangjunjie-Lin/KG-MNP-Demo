from __future__ import annotations

from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from kg_mnp.semantic_kernel.packaging.verifier import verify_package


class LocalRDFQueryAdapter:
    """Read-only query adapter over a verified package directory."""

    def __init__(self, package_root: Path | str, *, max_results: int = 1000):
        self.root = Path(package_root)
        if verify_package(self.root).get("status") != "VALID":
            raise ValueError("verified package required")
        self.max_results = max_results
        self.graph = Graph()
        for relative in ("ontology/effective-tbox.nt", "data/abox.nt", "shapes/effective-shapes.nt"):
            path = self.root / relative
            if path.is_file():
                self.graph.parse(path, format="nt")

    def _bounded(self, rows: list[dict[str, Any]], limit: int) -> dict[str, Any]:
        if limit < 1 or limit > self.max_results:
            raise ValueError("result limit is outside policy")
        return {"rows": rows[:limit], "returned": min(len(rows), limit), "truncated": len(rows) > limit}

    def instances_by_class(self, class_iri: str, *, limit: int = 100) -> dict[str, Any]:
        rows = [{"iri": str(subject)} for subject in self.graph.subjects(RDF.type, URIRef(class_iri)) if isinstance(subject, URIRef)]
        return self._bounded(rows, limit)

    def instance(self, iri: str, *, limit: int = 100) -> dict[str, Any]:
        rows = [{"predicate": str(predicate), "object": self._term(obj)} for predicate, obj in self.graph.predicate_objects(URIRef(iri))]
        return self._bounded(rows, limit)

    def property_filter(self, predicate: str, value: Any, *, limit: int = 100) -> dict[str, Any]:
        wanted = Literal(value) if not isinstance(value, (URIRef, Literal)) else value
        rows = [{"iri": str(subject)} for subject in self.graph.subjects(URIRef(predicate), wanted) if isinstance(subject, URIRef)]
        return self._bounded(rows, limit)

    def neighbors(self, iri: str, *, depth: int = 1, limit: int = 100) -> dict[str, Any]:
        if depth < 1 or depth > 2:
            raise ValueError("neighbor depth is bounded to one or two")
        frontier = {URIRef(iri)}
        seen = set(frontier)
        for _ in range(depth):
            next_frontier = set()
            for node in frontier:
                next_frontier.update(obj for obj in self.graph.objects(node) if isinstance(obj, URIRef))
                next_frontier.update(subject for subject in self.graph.subjects(None, node) if isinstance(subject, URIRef))
            frontier = next_frontier - seen
            seen.update(frontier)
        return self._bounded([{"iri": str(node)} for node in sorted(seen, key=str) if isinstance(node, URIRef)], limit)

    @staticmethod
    def _term(term):
        if isinstance(term, Literal):
            return {"term_type": "LITERAL", "value": str(term), "datatype": str(term.datatype) if term.datatype else None, "language": term.language}
        return {"term_type": "IRI", "value": str(term)}
