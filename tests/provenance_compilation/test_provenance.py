from __future__ import annotations

import copy

from prompt05_support import candidate
from rdflib import RDF, URIRef

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.semantic_kernel.provenance import compile_statement_provenance
from kg_mnp.semantic_kernel.validators.provenance import validate_provenance_closure


def test_statement_provenance_and_evidence_lineage_closure() -> None:
    value = candidate("INDIVIDUAL", candidate_kind="ABOX", candidate_action="ASSERT", subject_iri="urn:test:entity")
    candidate_id = value["candidate_id"]
    evidence_id = value["evidence_refs"][0]
    kgir_id = value["kg_ir_item_refs"][0]
    source_id = stable_urn("source-asset", {"source": 1})
    plugin_id = stable_urn("plugin-snapshot", {"plugin": 1})
    transformation_id = stable_urn("transformation-record", {"step": 1})
    review_id = stable_urn("ontology-review-decision-log", {"review": 1})
    snapshot_id = stable_urn("semantic-compiler-snapshot", {"snapshot": 1})
    plan_id = stable_urn("semantic-compilation-plan", {"plan": 1})
    resolved = {
        evidence_id: {"source_id": source_id, "plugin_snapshot_id": plugin_id, "transformation_ids": [transformation_id]},
        source_id: {"content_sha256": "a" * 64},
        kgir_id: {"item_id": kgir_id},
        plugin_id: {"snapshot_id": plugin_id},
        transformation_id: {"transformation_id": transformation_id},
    }
    triple = (URIRef("urn:test:entity"), RDF.type, URIRef("http://www.w3.org/2002/07/owl#NamedIndividual"))
    graph, _, manifest = compile_statement_provenance(
        candidates={candidate_id: value},
        item_triples={candidate_id: (triple,)},
        item_graph_iris={candidate_id: "abox|urn:test:graph"},
        review_decision_id=review_id,
        review_semantic_hash="b" * 64,
        compiler_snapshot_id=snapshot_id,
        plan_id=plan_id,
        resolved_artifacts=resolved,
        baseline_statement_sources={},
        baseline_graph_iris={"effective-tbox": "urn:test:tbox", "effective-shapes": "urn:test:shapes"},
    )
    known = {candidate_id, evidence_id, kgir_id, source_id, plugin_id, transformation_id, review_id, snapshot_id, plan_id}
    report = validate_provenance_closure(
        manifest,
        known_artifact_ids=known,
        project_artifact_ids=known,
        candidates={candidate_id: value},
        resolved_artifacts=resolved,
        packaged_baseline_paths=set(),
    )
    assert len(graph) > 0
    assert report["status"] == "PASSED" and report["coverage_basis_points"] == 10000
    broken = copy.deepcopy(manifest)
    broken["statements"][0]["source_asset_refs"] = [stable_urn("source-asset", {"missing": 1})]
    failed = validate_provenance_closure(
        broken,
        known_artifact_ids=known,
        project_artifact_ids=known,
        candidates={candidate_id: value},
        resolved_artifacts=resolved,
        packaged_baseline_paths=set(),
    )
    assert failed["status"] == "FAILED" and failed["missing_links"]


def test_baseline_provenance_requires_packaged_assets() -> None:
    manifest = {
        "statements": [
            {
                "statement_id": stable_urn("semantic-statement", {"baseline": 1}),
                "provenance_class": "BASELINE_REUSED",
                "compiler_snapshot_id": stable_urn("semantic-compiler-snapshot", {"snapshot": 1}),
                "confirmed_item_id": None,
                "source_candidate_id": None,
                "review_decision_id": None,
                "review_semantic_hash": None,
                "provider_snapshot_refs": [],
                "kg_ir_item_refs": [],
                "evidence_record_refs": [],
                "source_asset_refs": [],
                "domain_pack_asset_refs": ["baseline/assets/missing.ttl"],
            }
        ]
    }
    snapshot = manifest["statements"][0]["compiler_snapshot_id"]
    report = validate_provenance_closure(manifest, known_artifact_ids={snapshot}, project_artifact_ids={snapshot}, candidates={}, resolved_artifacts={}, packaged_baseline_paths=set())
    assert report["status"] == "FAILED"

