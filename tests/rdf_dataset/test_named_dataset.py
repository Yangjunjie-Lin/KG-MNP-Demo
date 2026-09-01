from __future__ import annotations

from rdflib import Dataset, Graph, Literal, URIRef

from kg_mnp.semantic_kernel.identifiers import graph_iri
from kg_mnp.semantic_kernel.rdf.canonical import canonical_nquads
from kg_mnp.semantic_kernel.rdf.dataset import build_named_dataset


def _dataset_quads(data: bytes, rdf_format: str) -> bytes:
    dataset = Dataset().parse(data=data.decode(), format=rdf_format)
    quads = []
    for subject, predicate, obj, context in dataset.quads((None, None, None, None)):
        graph = context.identifier if hasattr(context, "identifier") else context
        quads.append((subject, predicate, obj, graph))
    return canonical_nquads(quads)


def test_named_graph_roles_ids_counts_and_serializations_are_deterministic() -> None:
    abox = Graph()
    abox.add((URIRef("urn:test:entity"), URIRef("urn:test:label"), Literal("Entity")))
    tbox = Graph()
    tbox.add((URIRef("urn:test:Class"), URIRef("urn:test:type"), URIRef("urn:test:Meta")))
    package_id = "urn:kg-mnp:ontology-package:" + "a" * 64
    first = build_named_dataset(package_identity_basis=package_id, graphs_by_role={"effective-tbox": tbox, "abox": abox})
    second = build_named_dataset(package_identity_basis=package_id, graphs_by_role={"abox": abox, "effective-tbox": tbox})
    manifest, nq, trig, graph_iris = first
    assert first[:3] == second[:3]
    assert manifest["total_quad_count"] == 2
    assert _dataset_quads(nq, "nquads") == _dataset_quads(trig, "trig")
    for row in manifest["graphs"]:
        assert row["graph_iri"] == graph_iri(package_id, row["role"], row["graph_semantic_digest"])
        assert graph_iris[row["role"]] == row["graph_iri"]

