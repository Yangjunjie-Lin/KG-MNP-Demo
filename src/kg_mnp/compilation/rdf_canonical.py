"""Legacy Stage 06 wrapper over the Prompt 5 canonical RDF primitive."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from rdflib import Graph, URIRef

from kg_mnp.semantic_kernel.rdf.canonical import (
    CanonicalRDFError,
    Quad,
    Triple,
    assert_no_blank_nodes,
    canonical_nquads,
    canonical_ntriples,
    canonical_term,
    graph_semantic_digest,
)

# The historical readable Stage 06 view retains its MNP prefix and exact prefix
# order. New semantic-kernel callers use domain-neutral configurable prefixes.
PREFIXES = (
    ("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    ("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
    ("owl", "http://www.w3.org/2002/07/owl#"),
    ("xsd", "http://www.w3.org/2001/XMLSchema#"),
    ("sh", "http://www.w3.org/ns/shacl#"),
    ("dcterms", "http://purl.org/dc/terms/"),
    ("skos", "http://www.w3.org/2004/02/skos/core#"),
    ("mnp", "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#"),
)


def canonical_rdf_term(term):
    return canonical_term(term)


def parse_ntriples(data: bytes | str) -> Graph:
    graph = Graph()
    graph.parse(data=data.decode("utf-8") if isinstance(data, bytes) else data, format="nt")
    assert_no_blank_nodes(graph)
    return graph


def semantic_sha256_rdf(data: bytes, *, format: str) -> str:
    graph = Graph()
    graph.parse(data=data.decode("utf-8"), format=format)
    return graph_semantic_digest(graph)


def deterministic_turtle(triples: Iterable[Triple] | Graph) -> bytes:
    values = list(triples.triples((None, None, None))) if isinstance(triples, Graph) else list(triples)
    prefix_lines = [f"@prefix {name}: <{iri}> ." for name, iri in PREFIXES]
    body = [f"{canonical_term(s)} {canonical_term(p)} {canonical_term(o)} ." for s, p, o in values]
    return ("\n".join([*prefix_lines, "", *sorted(set(body))]) + "\n").encode()


def deterministic_trig(graphs: Mapping[URIRef | str, Iterable[Triple] | Graph]) -> bytes:
    prefix_lines = [f"@prefix {name}: <{iri}> ." for name, iri in PREFIXES]
    sections: list[str] = []
    for graph_iri, triples in sorted(graphs.items(), key=lambda item: str(item[0])):
        values = list(triples.triples((None, None, None))) if isinstance(triples, Graph) else list(triples)
        lines = sorted({f"{canonical_term(s)} {canonical_term(p)} {canonical_term(o)} ." for s, p, o in values})
        sections.append(f"<{graph_iri}> {{")
        sections.extend(f"  {line}" for line in lines)
        sections.extend(("}", ""))
    return ("\n".join([*prefix_lines, "", *sections]).rstrip() + "\n").encode()


__all__ = [
    "PREFIXES",
    "CanonicalRDFError",
    "Quad",
    "Triple",
    "assert_no_blank_nodes",
    "canonical_nquads",
    "canonical_ntriples",
    "canonical_rdf_term",
    "deterministic_trig",
    "deterministic_turtle",
    "parse_ntriples",
    "semantic_sha256_rdf",
]
