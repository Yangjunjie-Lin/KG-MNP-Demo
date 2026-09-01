"""Canonical N-Triples and N-Quads without runtime blank-node labels."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from rdflib import BNode, Graph, Literal
from rdflib.plugins.serializers.nt import _quoteLiteral
from rdflib.term import Identifier

Triple = tuple[Identifier, Identifier, Identifier]
Quad = tuple[Identifier, Identifier, Identifier, Identifier]


class CanonicalRDFError(ValueError):
    pass


def canonical_term(term: Identifier) -> str:
    if isinstance(term, BNode):
        raise CanonicalRDFError("blank nodes are forbidden in authoritative compiled RDF")
    if isinstance(term, Literal):
        return _quoteLiteral(term)
    return term.n3()


def canonical_ntriples(values: Iterable[Triple] | Graph) -> bytes:
    triples = values.triples((None, None, None)) if isinstance(values, Graph) else values
    lines = {f"{canonical_term(s)} {canonical_term(p)} {canonical_term(o)} ." for s, p, o in triples}
    return ("\n".join(sorted(lines)) + ("\n" if lines else "")).encode()


def canonical_nquads(values: Iterable[Quad]) -> bytes:
    rows = {
        (
            canonical_term(g), canonical_term(s), canonical_term(p), canonical_term(o),
            f"{canonical_term(s)} {canonical_term(p)} {canonical_term(o)} {canonical_term(g)} .",
        )
        for s, p, o, g in values
    }
    return ("\n".join(row[4] for row in sorted(rows)) + ("\n" if rows else "")).encode()


def graph_semantic_digest(graph: Graph) -> str:
    return hashlib.sha256(canonical_ntriples(graph)).hexdigest()


def dataset_semantic_digest(quads: Iterable[Quad]) -> str:
    return hashlib.sha256(canonical_nquads(quads)).hexdigest()


def assert_no_blank_nodes(graph: Graph) -> None:
    if any(isinstance(term, BNode) for triple in graph for term in triple):
        raise CanonicalRDFError("blank nodes are forbidden in authoritative compiled RDF")
