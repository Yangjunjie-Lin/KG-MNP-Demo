"""Deterministic readable Turtle and TriG projections."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from rdflib import Graph, URIRef

from .canonical import Triple, canonical_term

STANDARD_PREFIXES = (
    ("dcterms", "http://purl.org/dc/terms/"),
    ("owl", "http://www.w3.org/2002/07/owl#"),
    ("prov", "http://www.w3.org/ns/prov#"),
    ("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    ("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
    ("sh", "http://www.w3.org/ns/shacl#"),
    ("xsd", "http://www.w3.org/2001/XMLSchema#"),
)


def normalized_prefixes(
    extra: Mapping[str, str] | Iterable[tuple[str, str]] = (),
) -> tuple[tuple[str, str], ...]:
    values = dict(STANDARD_PREFIXES)
    items = extra.items() if isinstance(extra, Mapping) else extra
    for name, iri in items:
        if not name.replace("_", "").isalnum() or not name[0].isalpha():
            raise ValueError("unsafe RDF prefix")
        existing = values.get(name)
        if existing is not None and existing != iri:
            raise ValueError(f"RDF prefix collision: {name}")
        values[name] = iri
    return tuple(sorted(values.items()))


def deterministic_turtle(
    triples: Iterable[Triple] | Graph,
    *,
    prefixes: Mapping[str, str] | Iterable[tuple[str, str]] = (),
) -> bytes:
    values = triples.triples((None, None, None)) if isinstance(triples, Graph) else triples
    prefix_lines = [f"@prefix {name}: <{iri}> ." for name, iri in normalized_prefixes(prefixes)]
    lines = sorted({f"{canonical_term(s)} {canonical_term(p)} {canonical_term(o)} ." for s, p, o in values})
    return ("\n".join([*prefix_lines, "", *lines]) + "\n").encode()


def deterministic_trig(
    graphs: Mapping[URIRef | str, Iterable[Triple] | Graph],
    *,
    prefixes: Mapping[str, str] | Iterable[tuple[str, str]] = (),
) -> bytes:
    output = [f"@prefix {name}: <{iri}> ." for name, iri in normalized_prefixes(prefixes)]
    output.append("")
    for graph_iri, graph in sorted(graphs.items(), key=lambda item: str(item[0])):
        values = graph.triples((None, None, None)) if isinstance(graph, Graph) else graph
        lines = sorted({f"{canonical_term(s)} {canonical_term(p)} {canonical_term(o)} ." for s, p, o in values})
        output.append(f"<{graph_iri}> {{")
        output.extend(f"  {line}" for line in lines)
        output.extend(("}", ""))
    return ("\n".join(output).rstrip() + "\n").encode()
