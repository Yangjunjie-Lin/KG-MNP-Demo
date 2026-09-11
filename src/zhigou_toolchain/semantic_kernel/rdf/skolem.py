"""Deterministic structure-based baseline and RDF-list skolemization."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from rdflib import BNode, Graph, URIRef
from rdflib.compare import to_canonical_graph

from .canonical import canonical_term


def skolemize_graph(graph: Graph, *, namespace: str = "urn:kg-mnp:baseline-skolem:") -> Graph:
    """Canonicalize a graph then replace structural blank nodes with stable IRIs."""

    canonical = to_canonical_graph(graph)
    identifiers = sorted(
        {term for triple in canonical for term in triple if isinstance(term, BNode)},
        key=str,
    )
    replacements = {
        value: URIRef(namespace + hashlib.sha256(str(value).encode()).hexdigest())
        for value in identifiers
    }
    result = Graph()
    for subject, predicate, obj in canonical:
        result.add((replacements.get(subject, subject), predicate, replacements.get(obj, obj)))
    return result


def rdf_list_nodes(values: Iterable[object], *, owner_iri: str) -> tuple[URIRef, ...]:
    encoded = tuple(canonical_term(value) for value in values)
    return tuple(
        URIRef(
            "urn:kg-mnp:shacl-list-node:"
            + hashlib.sha256(f"{owner_iri}\n{index}\n{encoded}".encode()).hexdigest()
        )
        for index, _ in enumerate(encoded)
    )
