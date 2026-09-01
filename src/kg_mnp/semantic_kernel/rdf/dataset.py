"""Canonical named-graph dataset construction."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from rdflib import Graph, URIRef

from ..contracts import finalize_artifact
from ..identifiers import graph_iri
from .canonical import canonical_nquads, graph_semantic_digest
from .serializers import deterministic_trig


def build_named_dataset(
    *,
    package_identity_basis: str,
    graphs_by_role: Mapping[str, Graph],
    source_counts: Mapping[str, int] | None = None,
    coverage: Mapping[str, int] | None = None,
) -> tuple[dict[str, Any], bytes, bytes, dict[str, str]]:

    graph_iris: dict[str, str] = {}
    manifest_rows = []
    quads = []
    trig_graphs = {}
    for role, graph in sorted(graphs_by_role.items()):
        digest = graph_semantic_digest(graph)
        iri = graph_iri(package_identity_basis, role, digest)
        graph_iris[role] = iri
        graph_ref = URIRef(iri)
        trig_graphs[graph_ref] = graph
        quads.extend((s, p, o, graph_ref) for s, p, o in graph)
        manifest_rows.append({
            "role": role,
            "graph_iri": iri,
            "triple_count": len(graph),
            "graph_semantic_digest": digest,
            "source_confirmed_item_count": int((source_counts or {}).get(role, 0)),
            "provenance_coverage_basis_points": int((coverage or {}).get(role, 10000)),
        })
    nq = canonical_nquads(quads)
    core = {
        "manifest_kind": "KG_MNP_RDF_DATASET_MANIFEST",
        "schema_version": "1.0.0",
        "graphs": manifest_rows,
        "total_quad_count": len(set(quads)),
        "dataset_semantic_digest": hashlib.sha256(nq).hexdigest(),
    }
    manifest = finalize_artifact(core, id_field="dataset_id", urn_kind="rdf-dataset-manifest", contract="rdf-dataset-manifest")
    return manifest, nq, deterministic_trig(trig_graphs), graph_iris
