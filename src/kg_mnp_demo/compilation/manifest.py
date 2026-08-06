"""Compilation manifest projection, artifact metadata, and self-hash."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from ..modeling.canonical_json import canonical_json_bytes, semantic_hash
from .identifiers import artifact_id, compilation_id


def compilation_manifest_semantic_content(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: manifest[key]
        for key in sorted(manifest)
        if key not in {"compilation_id", "compilation_semantic_hash"}
    }


def compilation_manifest_hash(manifest: Mapping[str, Any]) -> str:
    return semantic_hash(compilation_manifest_semantic_content(manifest))


def complete_manifest(content: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(content)
    digest = compilation_manifest_hash(result)
    result["compilation_semantic_hash"] = digest
    result["compilation_id"] = compilation_id(digest)
    return result


def artifact_record(
    relative_path: str,
    role: str,
    media_type: str,
    data: bytes,
    *,
    semantic_sha256: str | None = None,
    triple_count: int | None = None,
    quad_count: int | None = None,
) -> dict[str, Any]:
    byte_hash = hashlib.sha256(data).hexdigest()
    record: dict[str, Any] = {
        "relative_path": relative_path,
        "role": role,
        "media_type": media_type,
        "byte_sha256": byte_hash,
        "semantic_sha256": semantic_sha256 or byte_hash,
        "size_bytes": len(data),
    }
    if triple_count is not None:
        record["triple_count"] = triple_count
    if quad_count is not None:
        record["quad_count"] = quad_count
    record["artifact_id"] = artifact_id(record)
    return record


def json_semantic_hash(data: bytes) -> str:
    value = json.loads(data.decode("utf-8"))
    return semantic_hash(value)


def rdf_semantic_hash(data: bytes, suffix: str) -> str:
    """Hash RDF meaning rather than a human-readable serialization."""
    import hashlib
    from rdflib import Dataset, Graph
    from .rdf_canonical import canonical_nquads, canonical_ntriples

    if suffix in {".nq", ".trig"}:
        dataset = Dataset()
        dataset.parse(data=data.decode("utf-8"), format="nquads" if suffix == ".nq" else "trig")
        quads = [(s, p, o, g) for s, p, o, g in dataset.quads((None, None, None, None))]
        return hashlib.sha256(canonical_nquads(quads)).hexdigest()
    graph = Graph()
    graph.parse(data=data.decode("utf-8"), format="nt" if suffix == ".nt" else "turtle")
    return hashlib.sha256(canonical_ntriples(graph)).hexdigest()


def json_bytes(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"
