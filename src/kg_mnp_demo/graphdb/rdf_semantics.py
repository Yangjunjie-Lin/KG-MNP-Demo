"""GraphDB/RDF 1.1 semantic normalization without changing Stage 06 bytes."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from rdflib import BNode, Dataset, Literal
from rdflib.namespace import XSD
from rdflib.term import Identifier

from ..compilation.rdf_canonical import canonical_nquads


class GraphDBRDFSemanticError(ValueError):
    pass


Quad = tuple[Identifier, Identifier, Identifier, Identifier]


def _normalize_term(term: Identifier) -> Identifier:
    # RDF 1.1 simple literals and explicit xsd:string literals denote the
    # same RDF literal. GraphDB 11.4.2 serializes the latter as the former.
    if isinstance(term, Literal) and term.language is None and term.datatype == XSD.string:
        return Literal(str(term))
    return term


def graphdb_semantic_nquads(quads: Iterable[Quad]) -> bytes:
    normalized: list[Quad] = []
    for quad in quads:
        if len(quad) != 4:
            raise GraphDBRDFSemanticError("GraphDB semantic hash requires RDF quads")
        value = tuple(_normalize_term(term) for term in quad)
        if any(isinstance(term, BNode) for term in value):
            raise GraphDBRDFSemanticError("GraphDB semantic hash forbids blank nodes")
        normalized.append(value)  # type: ignore[arg-type]
    return canonical_nquads(normalized)


def graphdb_semantic_hash(quads: Iterable[Quad]) -> str:
    return hashlib.sha256(graphdb_semantic_nquads(quads)).hexdigest()


def graphdb_semantic_hash_nquads(data: bytes) -> str:
    dataset = Dataset()
    try:
        dataset.parse(data=data.decode("utf-8"), format="nquads")
    except Exception as exc:
        raise GraphDBRDFSemanticError("data is not valid N-Quads") from exc
    quads = list(dataset.quads((None, None, None, None)))
    return graphdb_semantic_hash(quads)
