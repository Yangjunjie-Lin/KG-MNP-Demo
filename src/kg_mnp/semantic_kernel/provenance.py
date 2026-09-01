"""Statement-level PROV-O/RDF reification owned by the toolchain namespace."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rdflib import PROV, RDF, Graph, Literal, URIRef

from .contracts import finalize_artifact
from .identifiers import semantic_id, statement_id
from .namespaces import KGP
from .rdf.canonical import canonical_term, graph_semantic_digest


def compile_statement_provenance(
    *,
    candidates: Mapping[str, dict[str, Any]],
    item_triples: Mapping[str, tuple[tuple[Any, Any, Any], ...]],
    item_graph_iris: Mapping[str, str],
    review_decision_id: str,
    review_semantic_hash: str,
    compiler_snapshot_id: str,
    plan_id: str,
    resolved_artifacts: Mapping[str, dict[str, Any]],
    baseline_statement_sources: Mapping[tuple[Any, Any, Any], tuple[dict, ...]],
    baseline_graph_iris: Mapping[str, str],
) -> tuple[Graph, Graph, dict[str, Any]]:
    graph = Graph()
    activity = URIRef(semantic_id("semantic-compilation-activity", {"plan_id": plan_id, "compiler_snapshot_id": compiler_snapshot_id}))
    graph.add((activity, RDF.type, KGP.CompilationActivity))
    graph.add((activity, PROV.used, URIRef(plan_id)))
    graph.add((activity, KGP.compilerSnapshot, URIRef(compiler_snapshot_id)))
    rows = []
    mapping_graph = Graph()
    for candidate_id, triples in sorted(item_triples.items()):
        candidate = candidates[candidate_id]
        role = item_graph_iris[candidate_id].split("|", 1)[0]
        graph_iri = item_graph_iris[candidate_id].split("|", 1)[1]
        for subject, predicate, obj in triples:
            identifier = statement_id(graph_role=role, subject=canonical_term(subject), predicate=canonical_term(predicate), object_term=canonical_term(obj))
            ref = URIRef(identifier)
            graph.add((ref, RDF.type, RDF.Statement))
            graph.add((ref, RDF.subject, subject))
            graph.add((ref, RDF.predicate, predicate))
            graph.add((ref, RDF.object, obj))
            graph.add((ref, KGP.confirmedItem, URIRef(candidate_id)))
            graph.add((ref, KGP.reviewDecision, URIRef(review_decision_id)))
            graph.add((ref, KGP.compilerSnapshot, URIRef(compiler_snapshot_id)))
            graph.add((ref, KGP.graphRole, Literal(role)))
            graph.add((ref, PROV.wasGeneratedBy, activity))
            if role == "mapping-provenance":
                for triple in graph.triples((ref, None, None)):
                    mapping_graph.add(triple)
            source_refs = sorted(
                {
                    source_id
                    for evidence_id in candidate["evidence_refs"]
                    for source_id in [resolved_artifacts.get(evidence_id, {}).get("source_id")]
                    if isinstance(source_id, str)
                }
            )
            rows.append({
                "statement_id": identifier,
                "subject": canonical_term(subject),
                "predicate": str(predicate),
                "object": canonical_term(obj),
                "graph_iri": graph_iri,
                "confirmed_item_id": candidate_id,
                "source_candidate_id": candidate_id,
                "review_decision_id": review_decision_id,
                "review_semantic_hash": review_semantic_hash,
                "provider_snapshot_refs": candidate["provider_snapshot_refs"],
                "kg_ir_item_refs": candidate["kg_ir_item_refs"],
                "evidence_record_refs": candidate["evidence_refs"],
                "source_asset_refs": source_refs,
                "domain_pack_asset_refs": candidate["domain_asset_refs"],
                "compilation_activity_id": str(activity),
                "compiler_snapshot_id": compiler_snapshot_id,
                "provenance_class": "GENERATED",
            })
    baseline_roles = {
        "effective-tbox": baseline_graph_iris["effective-tbox"],
        "effective-shapes": baseline_graph_iris["effective-shapes"],
    }
    for triple, sources in sorted(
        baseline_statement_sources.items(),
        key=lambda item: tuple(canonical_term(term) for term in item[0]),
    ):
        subject, predicate, obj = triple
        for role in sorted({source["graph_role"] for source in sources}):
            role_sources = [source for source in sources if source["graph_role"] == role]
            matching = [
                candidate
                for candidate in candidates.values()
                if candidate["candidate_action"] in {"REUSE_EXISTING", "ALIGN_TO_EXISTING"}
                and (
                    candidate["body"].get("subject_iri") in {str(subject), str(obj)}
                    or candidate["body"].get("target_iri") in {str(subject), str(obj)}
                )
            ]
            reuse = min(matching, key=lambda item: item["candidate_id"]) if matching else None
            identifier = statement_id(
                graph_role=role,
                subject=canonical_term(subject),
                predicate=canonical_term(predicate),
                object_term=canonical_term(obj),
            )
            ref = URIRef(identifier)
            graph.add((ref, RDF.type, RDF.Statement))
            graph.add((ref, RDF.subject, subject))
            graph.add((ref, RDF.predicate, predicate))
            graph.add((ref, RDF.object, obj))
            graph.add((ref, KGP.compilerSnapshot, URIRef(compiler_snapshot_id)))
            graph.add((ref, KGP.graphRole, Literal(role)))
            graph.add((ref, PROV.wasGeneratedBy, activity))
            if reuse is not None:
                graph.add((ref, KGP.confirmedItem, URIRef(reuse["candidate_id"])))
                graph.add((ref, KGP.reviewDecision, URIRef(review_decision_id)))
            for source in role_sources:
                graph.add((ref, KGP.baselineAsset, Literal(source["asset_path"])))
                graph.add((ref, KGP.packLock, URIRef(source["pack_lock_id"])))
            rows.append(
                {
                    "statement_id": identifier,
                    "subject": canonical_term(subject),
                    "predicate": str(predicate),
                    "object": canonical_term(obj),
                    "graph_iri": baseline_roles[role],
                    "confirmed_item_id": reuse["candidate_id"] if reuse else None,
                    "source_candidate_id": reuse["candidate_id"] if reuse else None,
                    "review_decision_id": review_decision_id if reuse else None,
                    "review_semantic_hash": review_semantic_hash if reuse else None,
                    "provider_snapshot_refs": reuse["provider_snapshot_refs"] if reuse else [],
                    "kg_ir_item_refs": reuse["kg_ir_item_refs"] if reuse else [],
                    "evidence_record_refs": reuse["evidence_refs"] if reuse else [],
                    "source_asset_refs": sorted(
                        {
                            source_id
                            for evidence_id in (reuse["evidence_refs"] if reuse else [])
                            for source_id in [resolved_artifacts.get(evidence_id, {}).get("source_id")]
                            if isinstance(source_id, str)
                        }
                    ),
                    "domain_pack_asset_refs": sorted(
                        {
                            value
                            for source in role_sources
                            for value in (source["asset_path"], source["lock_path"])
                        }
                    ),
                    "compilation_activity_id": str(activity),
                    "compiler_snapshot_id": compiler_snapshot_id,
                    "provenance_class": "BASELINE_REUSED",
                }
            )
    core = {"manifest_kind": "KG_MNP_STATEMENT_PROVENANCE_MANIFEST", "schema_version": "1.0.0", "plan_id": plan_id, "statements": sorted(rows, key=lambda item: item["statement_id"]), "statement_count": len(rows), "graph_semantic_sha256": graph_semantic_digest(graph)}
    manifest = finalize_artifact(core, id_field="provenance_manifest_id", urn_kind="statement-provenance-manifest", contract="statement-provenance-manifest")
    return graph, mapping_graph, manifest
