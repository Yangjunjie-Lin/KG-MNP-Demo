"""Bounded, local-only RDF parsing."""

from __future__ import annotations

from pathlib import Path

from rdflib import OWL, Graph, URIRef

from ..security import safe_child


def parse_rdf_bytes(data: bytes, *, format: str, max_bytes: int = 268_435_456) -> Graph:
    if len(data) > max_bytes:
        raise ValueError("RDF input exceeds configured byte limit")
    graph = Graph()
    graph.parse(data=data.decode("utf-8"), format=format)
    for value in graph.objects(None, OWL.imports):
        if isinstance(value, URIRef) and str(value).startswith(("http://", "https://")):
            raise ValueError("remote owl:imports requires an explicit local import catalog")
    return graph


def parse_local_rdf(root: Path, relative: str, *, format: str) -> Graph:
    path = safe_child(root, relative, must_exist=True)
    if not path.is_file():
        raise ValueError("unsafe RDF resource")
    return parse_rdf_bytes(path.read_bytes(), format=format)
