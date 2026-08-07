"""Deterministic RDF serialization for the Stage 06 authoritative artifacts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.plugins.serializers.nt import _quoteLiteral
from rdflib.term import Identifier

Triple = tuple[Identifier, Identifier, Identifier]
Quad = tuple[Identifier, Identifier, Identifier, Identifier]

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


class CanonicalRDFError(ValueError):
    pass


def _term(term: Identifier) -> str:
    if isinstance(term, BNode):
        raise CanonicalRDFError("blank nodes are forbidden in formal compiled RDF")
    if isinstance(term, Literal):
        return _quoteLiteral(term)
    return term.n3()


def canonical_rdf_term(term: Identifier) -> str:
    """Serialize one RDF term with the canonical Stage 06 safety policy."""

    return _term(term)


def canonical_ntriples(triples: Iterable[Triple] | Graph) -> bytes:
    values = triples.triples((None, None, None)) if isinstance(triples, Graph) else triples
    lines = {_term(s) + " " + _term(p) + " " + _term(o) + " ." for s, p, o in values}
    return (("\n".join(sorted(lines)) + "\n") if lines else "").encode("utf-8")


def canonical_nquads(quads: Iterable[Quad]) -> bytes:
    lines = {
        (_term(g), _term(s), _term(p), _term(o), f"{_term(s)} {_term(p)} {_term(o)} {_term(g)} .")
        for s, p, o, g in quads
    }
    ordered = [line[-1] for line in sorted(lines, key=lambda value: value[:4])]
    return (("\n".join(ordered) + "\n") if ordered else "").encode("utf-8")


def parse_ntriples(data: bytes | str) -> Graph:
    graph = Graph()
    graph.parse(data=data.decode("utf-8") if isinstance(data, bytes) else data, format="nt")
    if any(isinstance(term, BNode) for triple in graph for term in triple):
        raise CanonicalRDFError("blank nodes are forbidden in formal compiled RDF")
    return graph


def semantic_sha256_rdf(data: bytes, *, format: str) -> str:
    import hashlib
    graph = Graph()
    graph.parse(data=data.decode("utf-8"), format=format)
    return hashlib.sha256(canonical_ntriples(graph)).hexdigest()


def deterministic_turtle(triples: Iterable[Triple] | Graph) -> bytes:
    values = list(triples.triples((None, None, None))) if isinstance(triples, Graph) else list(triples)
    prefix_lines = [f"@prefix {name}: <{iri}> ." for name, iri in PREFIXES]
    body = [_term(s) + " " + _term(p) + " " + _term(o) + " ." for s, p, o in values]
    text = "\n".join([*prefix_lines, "", *sorted(set(body))]) + "\n"
    return text.encode("utf-8")


def deterministic_trig(graphs: Mapping[URIRef | str, Iterable[Triple] | Graph]) -> bytes:
    prefix_lines = [f"@prefix {name}: <{iri}> ." for name, iri in PREFIXES]
    sections: list[str] = []
    for graph_iri, triples in sorted(graphs.items(), key=lambda item: str(item[0])):
        values = list(triples.triples((None, None, None))) if isinstance(triples, Graph) else list(triples)
        lines = sorted({_term(s) + " " + _term(p) + " " + _term(o) + " ." for s, p, o in values})
        sections.append(f"<{graph_iri}> {{")
        sections.extend(f"  {line}" for line in lines)
        sections.append("}")
        sections.append("")
    return ("\n".join([*prefix_lines, "", *sections]).rstrip() + "\n").encode("utf-8")


def assert_no_blank_nodes(values: Iterable[Triple] | Iterable[Quad]) -> None:
    for value in values:
        if any(isinstance(term, BNode) for term in value):
            raise CanonicalRDFError("blank nodes are forbidden in formal compiled RDF")
