"""Evidence-lineage RDF that records references without inventing evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rdflib import PROV, Graph, Literal, URIRef

from .namespaces import KGP


def compile_evidence_lineage(
    *,
    provenance_manifest: dict[str, Any],
    resolved_artifacts: Mapping[str, dict[str, Any]],
) -> Graph:
    graph = Graph()
    for statement in provenance_manifest["statements"]:
        statement_ref = URIRef(statement["statement_id"])
        if statement["confirmed_item_id"] is None:
            continue
        candidate_ref = URIRef(statement["confirmed_item_id"])
        graph.add((statement_ref, PROV.wasDerivedFrom, candidate_ref))
        if statement["review_decision_id"] is not None:
            graph.add((candidate_ref, KGP.reviewDecision, URIRef(statement["review_decision_id"])))
        for kgir_id in statement["kg_ir_item_refs"]:
            graph.add((candidate_ref, KGP.sourceKGIRItem, URIRef(kgir_id)))
        for evidence_id in statement["evidence_record_refs"]:
            evidence_ref = URIRef(evidence_id)
            graph.add((candidate_ref, PROV.wasDerivedFrom, evidence_ref))
            evidence = resolved_artifacts.get(evidence_id, {})
            source_id = evidence.get("source_id") or evidence.get("source_asset_id")
            if isinstance(source_id, str) and source_id.startswith("urn:"):
                source_ref = URIRef(source_id)
                graph.add((evidence_ref, PROV.wasDerivedFrom, source_ref))
                source = resolved_artifacts.get(source_id, {})
                digest = source.get("content_sha256") or evidence.get("source_content_sha256")
                if isinstance(digest, str):
                    graph.add((source_ref, KGP.sourceBlobSha256, Literal(digest)))
            plugin = evidence.get("plugin_snapshot_id")
            if isinstance(plugin, str):
                graph.add((evidence_ref, KGP.parserSnapshot, URIRef(plugin)))
            for transformation in evidence.get("transformation_ids", []):
                graph.add((evidence_ref, KGP.transformation, URIRef(transformation)))
        for provider_id in statement["provider_snapshot_refs"]:
            graph.add((candidate_ref, PROV.wasAttributedTo, URIRef(provider_id)))
    return graph
