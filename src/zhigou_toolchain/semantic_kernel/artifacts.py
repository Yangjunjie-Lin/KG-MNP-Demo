"""Media-aware artifact hashing for ontology packages."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from zhigou_toolchain.contracts.canonical import semantic_hash

from .rdf.canonical import canonical_nquads, canonical_ntriples
from .rdf.skolem import skolemize_graph


def media_type_for_path(path: str) -> str:
    suffix = path.rsplit(".", 1)[-1].lower()
    return {
        "json": "application/json",
        "nt": "application/n-triples",
        "ttl": "text/turtle",
        "nq": "application/n-quads",
        "trig": "application/trig",
        "xml": "application/xml",
        "yaml": "application/yaml",
        "yml": "application/yaml",
        "rq": "application/sparql-query",
    }.get(suffix, "application/octet-stream")


def semantic_sha256(path: str, data: bytes) -> str:
    suffix = path.rsplit(".", 1)[-1].lower()
    if suffix == "json":
        return semantic_hash(json.loads(data))
    if suffix in {"nt", "ttl"}:
        from rdflib import Graph

        graph = Graph()
        graph.parse(data=data.decode(), format="nt" if suffix == "nt" else "turtle")
        return hashlib.sha256(canonical_ntriples(skolemize_graph(graph))).hexdigest()
    if suffix in {"nq", "trig"}:
        from rdflib import Dataset

        dataset = Dataset()
        dataset.parse(data=data.decode(), format="nquads" if suffix == "nq" else "trig")
        quads = []
        for s, p, o, context in dataset.quads((None, None, None, None)):
            graph = context.identifier if hasattr(context, "identifier") else context
            quads.append((s, p, o, graph))
        return hashlib.sha256(canonical_nquads(quads)).hexdigest()
    return hashlib.sha256(data).hexdigest()


def artifact_record(path: str, data: bytes, *, role: str) -> dict[str, Any]:
    return {"path": path, "role": role, "byte_sha256": hashlib.sha256(data).hexdigest(), "semantic_sha256": semantic_sha256(path, data), "size_bytes": len(data)}
