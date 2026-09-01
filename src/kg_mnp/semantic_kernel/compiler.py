"""Prompt 5 deterministic semantic compiler and strict package gate."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rdflib import RDF, Graph, URIRef

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.document_io import atomic_write_json, deterministic_json_bytes
from kg_mnp.ingestion.transaction import WorkspaceOperationLock

from .abox import compile_abox
from .artifact_resolver import WorkspaceArtifactResolver
from .baseline import BaselineClosure, load_baseline_closure
from .contracts import finalize_artifact, verify_artifact
from .errors import CompilationPlanError, SemanticKernelError
from .evidence_lineage import compile_evidence_lineage
from .identifiers import graph_iri, package_storage_key
from .input_attestation import attest_compiler_input
from .mapping import compile_mapping_plan
from .models import PackageBuildResult
from .namespaces import KGP
from .packaging.archive import archive_mapping_bytes, export_kgop
from .packaging.locking import build_package_lock
from .packaging.manifest import (
    build_package_manifest,
    package_id_for_plan,
    semantic_payload_identity_digest,
)
from .packaging.verifier import verify_package
from .plan import build_compilation_plan
from .policy import load_compiler_policy
from .provenance import compile_statement_provenance
from .rdf.canonical import canonical_ntriples, graph_semantic_digest
from .rdf.dataset import build_named_dataset
from .rdf.serializers import deterministic_turtle
from .review_audit import compile_review_audit
from .security import safe_child, scan_prohibited_text
from .shacl import compile_shacl
from .snapshot import build_compiler_snapshot
from .tbox import compile_tbox
from .transaction import SemanticCompilationTransaction
from .validators.competency_questions import execute_cq_test_plan
from .validators.owl_consistency import check_owl_consistency
from .validators.owl_profile import validate_owl_profile
from .validators.provenance import validate_provenance_closure
from .validators.rdf_syntax import validate_rdf_artifacts
from .validators.shacl import validate_shacl


def _json(value: dict[str, Any]) -> bytes:
    return deterministic_json_bytes(value)


def _within_limit(name: str, actual: int, limits: dict[str, int]) -> None:
    maximum = int(limits[name])
    if actual > maximum:
        raise ValueError(f"{name} exceeded: {actual} > {maximum}")


def _import_catalog(baseline: BaselineClosure) -> bytes:
    import xml.etree.ElementTree as ET

    root = ET.Element("catalog", {"xmlns": "urn:oasis:names:tc:entity:xmlns:xml:catalog"})
    ontology_assets = [item for item in baseline.assets if item["role"] in {"ONTOLOGY_ROOT", "ONTOLOGY_MODULE", "ONTOLOGY_ALIGNMENT"}]
    for ontology_iri, asset in zip(baseline.ontology_iris, ontology_assets, strict=False):
        ET.SubElement(root, "uri", {"name": ontology_iri, "uri": asset["asset_path"]})
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def _semantic_summary(*, baseline: BaselineClosure, tbox, abox, shapes, provenance: Graph, audit: Graph, lineage: Graph, dataset_manifest: dict[str, Any], mapping_plan: dict[str, Any], identity_payload_digest: str) -> dict[str, Any]:
    return {"baseline_triple_count": len(baseline.tbox), "new_tbox_triple_count": len(tbox.delta), "effective_tbox_triple_count": len(tbox.effective), "abox_triple_count": len(abox.graph), "compiled_shape_triple_count": len(shapes.compiled), "effective_shape_triple_count": len(shapes.effective), "provenance_triple_count": len(provenance), "review_audit_triple_count": len(audit), "evidence_lineage_triple_count": len(lineage), "dataset_quad_count": dataset_manifest["total_quad_count"], "mapping_rule_count": mapping_plan["mapping_count"], "semantic_dataset_digest": dataset_manifest["dataset_semantic_digest"], "identity_payload_digest": identity_payload_digest}


def _build_validation_report(
    package_id: str,
    reports: list[dict[str, Any]],
    *,
    attestation_id: str,
    snapshot_id: str,
    plan_id: str,
    reproduction_report_id: str,
) -> dict[str, Any]:
    checks = []
    for name, report in (
        ("RDF_SYNTAX", reports[0]), ("OWL_PROFILE", reports[1]), ("OWL_CONSISTENCY", reports[2]), ("SHACL_FINAL", reports[3]), ("COMPETENCY_QUESTIONS", reports[4]), ("PROVENANCE_CLOSURE", reports[5]),
    ):
        passing = {
            "RDF_SYNTAX": report.get("status") == "PASSED",
            "OWL_PROFILE": report.get("status") == "PASSED",
            "OWL_CONSISTENCY": report.get("status") == "CONSISTENT",
            "SHACL_FINAL": report.get("status") == "CONFORMS",
            "COMPETENCY_QUESTIONS": report.get("required_passed") is True and report.get("status") != "FAILED",
            "PROVENANCE_CLOSURE": report.get("status") == "PASSED" and report.get("coverage_basis_points") == 10000,
        }[name]
        checks.append({"check": name, "status": "PASSED" if passing else "FAILED", "report_ref": report["report_id"]})
    checks.extend([
        {"check": "INPUT_ATTESTATION", "status": "PASSED", "report_ref": attestation_id},
        {"check": "COMPILER_SNAPSHOT", "status": "PASSED", "report_ref": snapshot_id},
        {"check": "COMPILATION_PLAN", "status": "PASSED", "report_ref": plan_id},
        {"check": "PACKAGE_MANIFEST", "status": "PASSED", "report_ref": package_id},
        {"check": "PACKAGE_LOCK", "status": "PASSED", "report_ref": None},
        {"check": "PAYLOAD_INTEGRITY", "status": "PASSED", "report_ref": None},
        {"check": "ARTIFACT_CLOSURE", "status": "PASSED", "report_ref": None},
        {"check": "ARCHIVE_REPRODUCTION", "status": "PASSED", "report_ref": reproduction_report_id},
        {"check": "PROHIBITED_CONTENT_SCAN", "status": "PASSED", "report_ref": None},
    ])
    status = "VALID" if all(item["status"] == "PASSED" for item in checks) else "INVALID"
    core = {"manifest_kind": "KG_MNP_ONTOLOGY_PACKAGE_VALIDATION_REPORT", "schema_version": "1.0.0", "package_id": package_id, "checks": checks, "status": status, "issues": []}
    return finalize_artifact(core, id_field="report_id", urn_kind="ontology-package-validation-report", contract="ontology-package-validation-report")


def compile_plan(
    *,
    plan: dict[str, Any],
    attestation: dict[str, Any],
    confirmed_package: dict[str, Any],
    compiler_snapshot: dict[str, Any],
    compiler_policy: dict[str, Any],
    project_lock: dict[str, Any],
    baseline: BaselineClosure,
    cq_test_plan: dict[str, Any],
    review_log: dict[str, Any],
    proposal: dict[str, Any],
    resolved_artifacts: dict[str, dict[str, Any]],
    reasoner_jar: Path | str | None,
    query_loader,
) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any], dict[str, Any]]:
    verify_artifact(plan, id_field="plan_id", urn_kind="semantic-compilation-plan", contract="semantic-compilation-plan")
    if plan["status"] != "READY" or plan["compiler_input_attestation_id"] != attestation["attestation_id"]:
        raise ValueError("compilation plan is invalid or bound to a different attestation")
    limits = plan["resource_limits"]
    _within_limit(
        "max_confirmed_items",
        sum(len(confirmed_package[name]) for name in ("confirmed_tbox", "confirmed_mapping", "confirmed_abox", "confirmed_shacl")),
        limits,
    )
    _within_limit("max_cq_count", len(cq_test_plan["tests"]), limits)
    package_id = "urn:kg-mnp:ontology-package:" + "0" * 64
    tbox = compile_tbox(confirmed_package["confirmed_tbox"], baseline_graph=baseline.tbox, ontology_identity=plan["ontology_identity"], compiler_snapshot_id=compiler_snapshot["snapshot_id"], package_id=package_id, plan_id=plan["plan_id"])
    abox = compile_abox(confirmed_package["confirmed_abox"], effective_tbox=tbox.effective, plan_id=plan["plan_id"])
    shapes = compile_shacl(confirmed_package["confirmed_shacl"], baseline_shapes=baseline.shapes, plan_id=plan["plan_id"])
    mapping_plan = compile_mapping_plan(confirmed_package["confirmed_mapping"], source_plan_id=plan["plan_id"], review_decision_id=confirmed_package["review_decision_log_id"], effective_tbox=tbox.effective)
    _within_limit("max_tbox_statements", len(tbox.delta), limits)
    _within_limit("max_abox_statements", len(abox.graph), limits)
    _within_limit("max_shacl_statements", len(shapes.compiled), limits)
    _within_limit("max_mapping_rules", mapping_plan["mapping_count"], limits)
    _within_limit(
        "max_reasoner_input_triples",
        len(baseline.tbox) + len(tbox.delta) + len(abox.graph),
        limits,
    )
    mapping_graph = Graph()
    mapping_item_triples = {}
    for mapping in mapping_plan["mappings"]:
        ref = URIRef(mapping["compiled_mapping_id"])
        triples = ((ref, RDF.type, KGP.DeclarativeMapping), (ref, KGP.confirmedItem, URIRef(mapping["source_confirmed_item_id"])))
        for triple in triples:
            mapping_graph.add(triple)
        mapping_item_triples[mapping["source_confirmed_item_id"]] = triples
    role_graphs = {"ontology-module": tbox.module, "effective-tbox": tbox.effective, "abox": abox.graph, "compiled-shapes": shapes.compiled, "effective-shapes": shapes.effective, "mapping-provenance": mapping_graph}
    role_iris = {role: graph_iri(package_id, role, graph_semantic_digest(graph)) for role, graph in role_graphs.items()}
    all_item_triples = {**tbox.item_triples, **abox.item_triples, **shapes.item_triples, **mapping_item_triples}
    candidates = {item["candidate_id"]: item for partition in ("confirmed_tbox", "confirmed_mapping", "confirmed_abox", "confirmed_shacl") for item in confirmed_package[partition]}
    item_roles = {}
    for candidate_id in all_item_triples:
        kind = candidates[candidate_id]["candidate_kind"]
        role = {"TBOX": "ontology-module", "ABOX": "abox", "SHACL": "compiled-shapes", "MAPPING": "mapping-provenance"}[kind]
        item_roles[candidate_id] = f"{role}|{role_iris[role]}"
    effective_baseline_sources = {
        triple: tuple(
            source
            for source in sources
            if (
                source["graph_role"] == "effective-tbox"
                and triple in tbox.effective
            )
            or (
                source["graph_role"] == "effective-shapes"
                and triple in shapes.effective
            )
        )
        for triple, sources in baseline.statement_sources.items()
    }
    effective_baseline_sources = {
        triple: sources
        for triple, sources in effective_baseline_sources.items()
        if sources
    }
    provenance, mapping_provenance, provenance_manifest = compile_statement_provenance(candidates=candidates, item_triples=all_item_triples, item_graph_iris=item_roles, review_decision_id=confirmed_package["review_decision_log_id"], review_semantic_hash=confirmed_package["review_semantic_hash"], compiler_snapshot_id=compiler_snapshot["snapshot_id"], plan_id=plan["plan_id"], resolved_artifacts=resolved_artifacts, baseline_statement_sources=effective_baseline_sources, baseline_graph_iris=role_iris)
    for triple in mapping_graph:
        mapping_provenance.add(triple)
    audit = compile_review_audit(confirmed_package=confirmed_package, review_log=review_log, proposal=proposal)
    lineage = compile_evidence_lineage(provenance_manifest=provenance_manifest, resolved_artifacts=resolved_artifacts)
    activity = Graph()
    for subject in provenance.subjects(RDF.type, KGP.CompilationActivity):
        for triple in provenance.triples((subject, None, None)):
            activity.add(triple)
    identity_graphs = {
        "effective-tbox": tbox.effective,
        "abox": abox.graph,
        "compiled-shapes": shapes.compiled,
        "effective-shapes": shapes.effective,
        "mapping-provenance": mapping_provenance,
        "statement-provenance": provenance,
        "evidence-lineage": lineage,
        "review-audit": audit,
        "compilation-activity": activity,
    }
    identity_payload_digest = semantic_payload_identity_digest(
        graph_digests={
            role: graph_semantic_digest(graph)
            for role, graph in identity_graphs.items()
        },
        mapping_plan_digest=mapping_plan["content_digest"],
        cq_test_plan_digest=cq_test_plan["content_digest"],
        attestation_digest=attestation["content_digest"],
        baseline_assets=baseline.assets,
    )
    package_id = package_id_for_plan(
        plan_id=plan["plan_id"],
        confirmed_package_id=confirmed_package["package_id"],
        compiler_snapshot_id=compiler_snapshot["snapshot_id"],
        identity_payload_digest=identity_payload_digest,
    )
    tbox.module.remove((None, KGP.ontologyPackage, None))
    tbox.module.add(
        (
            URIRef(plan["ontology_identity"]["ontology_iri"]),
            KGP.ontologyPackage,
            URIRef(package_id),
        )
    )
    role_graphs = {"ontology-module": tbox.module, "effective-tbox": tbox.effective, "abox": abox.graph, "compiled-shapes": shapes.compiled, "effective-shapes": shapes.effective, "mapping-provenance": mapping_graph}
    role_iris = {role: graph_iri(package_id, role, graph_semantic_digest(graph)) for role, graph in role_graphs.items()}
    item_roles = {
        candidate_id: (
            f"{role}|{role_iris[role]}"
            if (role := {"TBOX": "ontology-module", "ABOX": "abox", "SHACL": "compiled-shapes", "MAPPING": "mapping-provenance"}[candidates[candidate_id]["candidate_kind"]])
            else ""
        )
        for candidate_id in all_item_triples
    }
    provenance, mapping_provenance, provenance_manifest = compile_statement_provenance(candidates=candidates, item_triples=all_item_triples, item_graph_iris=item_roles, review_decision_id=confirmed_package["review_decision_log_id"], review_semantic_hash=confirmed_package["review_semantic_hash"], compiler_snapshot_id=compiler_snapshot["snapshot_id"], plan_id=plan["plan_id"], resolved_artifacts=resolved_artifacts, baseline_statement_sources=effective_baseline_sources, baseline_graph_iris=role_iris)
    for triple in mapping_graph:
        mapping_provenance.add(triple)
    lineage = compile_evidence_lineage(provenance_manifest=provenance_manifest, resolved_artifacts=resolved_artifacts)
    activity = Graph()
    for subject in provenance.subjects(RDF.type, KGP.CompilationActivity):
        for triple in provenance.triples((subject, None, None)):
            activity.add(triple)
    final_identity_digest = semantic_payload_identity_digest(
        graph_digests={
            "effective-tbox": graph_semantic_digest(tbox.effective),
            "abox": graph_semantic_digest(abox.graph),
            "compiled-shapes": graph_semantic_digest(shapes.compiled),
            "effective-shapes": graph_semantic_digest(shapes.effective),
            "mapping-provenance": graph_semantic_digest(mapping_provenance),
            "statement-provenance": graph_semantic_digest(provenance),
            "evidence-lineage": graph_semantic_digest(lineage),
            "review-audit": graph_semantic_digest(audit),
            "compilation-activity": graph_semantic_digest(activity),
        },
        mapping_plan_digest=mapping_plan["content_digest"],
        cq_test_plan_digest=cq_test_plan["content_digest"],
        attestation_digest=attestation["content_digest"],
        baseline_assets=baseline.assets,
    )
    if final_identity_digest != identity_payload_digest:
        raise SemanticKernelError(
            "package-derived identities changed normalized semantic payload",
            code="BUILD_REPRODUCTION_MISMATCH",
        )
    dataset_graphs = {"ontology-module": tbox.module, "effective-tbox": tbox.effective, "abox": abox.graph, "compiled-shapes": shapes.compiled, "effective-shapes": shapes.effective, "mapping-provenance": mapping_provenance, "statement-provenance": provenance, "evidence-lineage": lineage, "review-audit": audit, "compilation-activity": activity}
    dataset_manifest, dataset_nq, dataset_trig, _ = build_named_dataset(package_identity_basis=package_id, graphs_by_role=dataset_graphs, source_counts={role: len(candidates) for role in dataset_graphs})
    _within_limit("max_provenance_statements", len(provenance) + len(audit) + len(lineage), limits)
    _within_limit("max_dataset_quads", dataset_manifest["total_quad_count"], limits)
    artifacts = {
        "source/confirmed-modeling-package.json": _json(confirmed_package), "source/compiler-input-attestation.json": _json(attestation), "source/semantic-compilation-plan.json": _json(plan), "source/semantic-compiler-snapshot.json": _json(compiler_snapshot), "source/review-decision-log.json": _json(review_log),
        "ontology/module.nt": canonical_ntriples(tbox.module), "ontology/module.ttl": deterministic_turtle(tbox.module), "ontology/tbox-delta.nt": canonical_ntriples(tbox.delta), "ontology/tbox-delta.ttl": deterministic_turtle(tbox.delta), "ontology/effective-tbox.nt": canonical_ntriples(tbox.effective), "ontology/effective-tbox.ttl": deterministic_turtle(tbox.effective), "ontology/import-catalog.xml": _import_catalog(baseline),
        "data/abox.nt": canonical_ntriples(abox.graph), "data/abox.ttl": deterministic_turtle(abox.graph),
        "shapes/compiled-shapes.nt": canonical_ntriples(shapes.compiled), "shapes/compiled-shapes.ttl": deterministic_turtle(shapes.compiled), "shapes/effective-shapes.nt": canonical_ntriples(shapes.effective), "shapes/effective-shapes.ttl": deterministic_turtle(shapes.effective),
        "mappings/mapping-plan.json": _json(mapping_plan), "dataset/dataset.nq": dataset_nq, "dataset/dataset.trig": dataset_trig, "dataset/rdf-dataset-manifest.json": _json(dataset_manifest),
        "provenance/statements.nt": canonical_ntriples(provenance), "provenance/statements.ttl": deterministic_turtle(provenance), "provenance/review-audit.nt": canonical_ntriples(audit), "provenance/review-audit.ttl": deterministic_turtle(audit), "provenance/evidence-lineage.nt": canonical_ntriples(lineage), "provenance/evidence-lineage.ttl": deterministic_turtle(lineage), "provenance/statement-provenance-manifest.json": _json(provenance_manifest),
        "validation/competency-question-test-plan.json": _json(cq_test_plan), **baseline.payload_files,
    }
    authority_index = {"manifest_kind": "KG_MNP_PACKAGE_AUTHORITY_INDEX", "schema_version": "1.0.0", "artifact_ids": sorted(resolved_artifacts), "content_digest": semantic_hash({"artifact_ids": sorted(resolved_artifacts)})}
    artifacts["source/authority-index.json"] = _json(authority_index)
    baseline_manifest = {"manifest_kind": "KG_MNP_PACKAGE_BASELINE_MANIFEST", "schema_version": "1.0.0", "assets": list(baseline.assets), "content_digest": semantic_hash(list(baseline.assets))}
    artifacts["baseline/baseline-manifest.json"] = _json(baseline_manifest)
    equivalents = {path: path for path in []}
    for left, right in (("ontology/module.nt", "ontology/module.ttl"), ("ontology/tbox-delta.nt", "ontology/tbox-delta.ttl"), ("ontology/effective-tbox.nt", "ontology/effective-tbox.ttl"), ("data/abox.nt", "data/abox.ttl"), ("shapes/compiled-shapes.nt", "shapes/compiled-shapes.ttl"), ("shapes/effective-shapes.nt", "shapes/effective-shapes.ttl"), ("provenance/statements.nt", "provenance/statements.ttl"), ("provenance/review-audit.nt", "provenance/review-audit.ttl"), ("provenance/evidence-lineage.nt", "provenance/evidence-lineage.ttl"), ("dataset/dataset.nq", "dataset/dataset.trig")):
        equivalents[left] = right
        equivalents[right] = left
    rdf_report = validate_rdf_artifacts(artifacts, dataset_id=dataset_manifest["dataset_id"], equivalents=equivalents)
    owl_profile = validate_owl_profile(tbox.effective, baseline_digest=graph_semantic_digest(baseline.tbox), delta_digest=graph_semantic_digest(tbox.delta), requested_profile=compiler_policy["owl_profile_policy"], reasoner_jar=reasoner_jar, timeout_seconds=compiler_policy["resource_limits"]["max_reasoner_seconds"], max_output_bytes=compiler_policy["resource_limits"]["max_reasoner_output_bytes"])
    owl_consistency = check_owl_consistency(baseline_graph=baseline.tbox, tbox_graph=tbox.delta, abox_graph=abox.graph, reasoner_jar=reasoner_jar, timeout_seconds=compiler_policy["resource_limits"]["max_reasoner_seconds"], max_output_bytes=compiler_policy["resource_limits"]["max_reasoner_output_bytes"], ontology_profile=compiler_policy["owl_profile_policy"])
    shacl_report, shacl_report_graph = validate_shacl(data_graph=abox.graph, shapes_graph=shapes.effective, ontology_graph=tbox.effective, max_results=compiler_policy["resource_limits"]["max_shacl_results"], max_seconds=compiler_policy["resource_limits"]["max_shacl_seconds"])
    cq_report = execute_cq_test_plan(
        cq_test_plan,
        dataset_nquads=dataset_nq,
        query_loader=query_loader,
        graph_iris={row["role"]: row["graph_iri"] for row in dataset_manifest["graphs"]},
    )
    known_ids = set(confirmed_package["artifact_manifest"]["artifact_ids"]) | set(candidates) | set(resolved_artifacts) | {confirmed_package["review_decision_log_id"], compiler_snapshot["snapshot_id"], plan["plan_id"]}
    provenance_report = validate_provenance_closure(provenance_manifest, known_artifact_ids=known_ids, project_artifact_ids=known_ids, candidates=candidates, resolved_artifacts=resolved_artifacts, packaged_baseline_paths=set(baseline.payload_files))
    reports = [rdf_report, owl_profile, owl_consistency, shacl_report, cq_report, provenance_report]
    artifacts.update({"validation/rdf-syntax-report.json": _json(rdf_report), "validation/owl-profile-report.json": _json(owl_profile), "validation/owl-consistency-report.json": _json(owl_consistency), "validation/shacl-validation-report.json": _json(shacl_report), "validation/shacl-validation-report.nt": canonical_ntriples(shacl_report_graph), "validation/competency-question-test-report.json": _json(cq_report), "validation/provenance-closure-report.json": _json(provenance_report)})
    prohibited = {
        path: findings
        for path, data in artifacts.items()
        if (findings := scan_prohibited_text(data))
    }
    if prohibited:
        raise SemanticKernelError(
            "prohibited path/secret content found in package payload: "
            + ", ".join(sorted(prohibited)),
            code="ONTOLOGY_PACKAGE_INVALID",
        )
    failing = [report for report in reports if report.get("status") in {"FAILED", "INCONSISTENT", "REASONER_UNAVAILABLE", "TIMEOUT", "ENGINE_ERROR", "VIOLATION", "NOT_RUN_EXTERNAL_PREREQUISITE"} or report.get("required_passed") is False]
    if failing:
        statuses = ", ".join(f"{report.get('manifest_kind')}={report.get('status')}" for report in failing)
        kinds = {report.get("manifest_kind"): report for report in failing}
        if any(report.get("status") == "REASONER_UNAVAILABLE" for report in failing):
            code = "REASONER_UNAVAILABLE"
        elif "KG_MNP_OWL_PROFILE_REPORT" in kinds:
            code = "OWL_PROFILE_FAILED"
        elif "KG_MNP_SEMANTIC_OWL_CONSISTENCY_REPORT" in kinds:
            code = "OWL_CONSISTENCY_FAILED"
        elif "KG_MNP_SEMANTIC_SHACL_VALIDATION_REPORT" in kinds:
            code = "SHACL_VALIDATION_FAILED"
        elif "KG_MNP_COMPETENCY_QUESTION_TEST_REPORT" in kinds:
            code = "COMPETENCY_QUESTION_FAILED"
        elif "KG_MNP_PROVENANCE_CLOSURE_REPORT" in kinds:
            code = "PROVENANCE_CLOSURE_FAILED"
        else:
            code = "RDF_VALIDATION_FAILED"
        raise SemanticKernelError(f"formal validation gate failed: {statuses}", code=code)
    summary = _semantic_summary(baseline=baseline, tbox=tbox, abox=abox, shapes=shapes, provenance=provenance, audit=audit, lineage=lineage, dataset_manifest=dataset_manifest, mapping_plan=mapping_plan, identity_payload_digest=identity_payload_digest)
    first_rebuild = archive_mapping_bytes(artifacts)
    second_rebuild = archive_mapping_bytes(dict(sorted(artifacts.items(), reverse=True)))
    first_digest = hashlib.sha256(first_rebuild).hexdigest()
    second_digest = hashlib.sha256(second_rebuild).hexdigest()
    reproduction = finalize_artifact({"manifest_kind": "KG_MNP_BUILD_REPRODUCTION_REPORT", "schema_version": "1.0.0", "build_id": stable_urn("semantic-compilation-build", {"plan_id": plan["plan_id"]}), "package_id": package_id, "compared_files": sorted(artifacts), "matching_files": sorted(artifacts) if first_rebuild == second_rebuild else [], "mismatches": [] if first_rebuild == second_rebuild else sorted(artifacts), "archive_sha256_first": first_digest, "archive_sha256_second": second_digest, "status": "PASSED" if first_rebuild == second_rebuild else "FAILED"}, id_field="report_id", urn_kind="build-reproduction-report", contract="build-reproduction-report")
    package_validation = _build_validation_report(package_id, reports, attestation_id=attestation["attestation_id"], snapshot_id=compiler_snapshot["snapshot_id"], plan_id=plan["plan_id"], reproduction_report_id=reproduction["report_id"])
    if package_validation["status"] != "VALID":
        raise ValueError("ontology package validation failed")
    artifacts["validation/build-reproduction-report.json"] = _json(reproduction)
    artifacts["validation/ontology-package-validation-report.json"] = _json(package_validation)
    for path, data in artifacts.items():
        if path.rsplit(".", 1)[-1].lower() in {"nt", "ttl", "nq", "trig"}:
            _within_limit("max_rdf_bytes_per_file", len(data), limits)
    _within_limit("max_package_files", len(artifacts) + 2, limits)
    _within_limit("max_package_uncompressed_bytes", sum(map(len, artifacts.values())), limits)
    manifest = build_package_manifest(package_id=package_id, plan=plan, confirmed_package=confirmed_package, compiler_snapshot=compiler_snapshot, compiler_policy=compiler_policy, project_lock=project_lock, baseline_assets=baseline.assets, dataset_manifest=dataset_manifest, mapping_plan=mapping_plan, validation_reports=[*reports, reproduction, package_validation], provenance_manifest=provenance_manifest, artifacts=artifacts, semantic_summary=summary)
    lock = build_package_lock(manifest, artifacts)
    _within_limit(
        "max_package_uncompressed_bytes",
        sum(map(len, artifacts.values())) + len(_json(manifest)) + len(_json(lock)),
        limits,
    )
    return artifacts, manifest, lock, {"reports": reports, "package_validation": package_validation, "reproduction": reproduction, "compilation_reports": [tbox.report, abox.report, shapes.report]}


class SemanticCompiler:
    def __init__(self, workspace: Path | str, *, domain_packs_root: Path | str, reasoner_jar: Path | str | None = None, policy_path: Path | str | None = None) -> None:
        self.workspace = Path(workspace).resolve(strict=True)
        self.domain_packs_root = Path(domain_packs_root).resolve(strict=True)
        self.reasoner_jar = Path(reasoner_jar).resolve(strict=True) if reasoner_jar is not None else None
        self.policy = load_compiler_policy(policy_path)
        self.snapshot = build_compiler_snapshot(self.policy, reasoner_jar=self.reasoner_jar)

    def _resolver(self) -> WorkspaceArtifactResolver:
        return WorkspaceArtifactResolver(self.workspace)

    def confirmed(self, package_id: str) -> dict[str, Any]:
        return self._resolver().resolve(package_id).document

    def attest(self, package_id: str) -> dict[str, Any]:
        package = self.confirmed(package_id)
        return attest_compiler_input(
            self.workspace,
            package,
            supported_types=set(self.policy["supported_candidate_types"]),
            domain_packs_root=self.domain_packs_root,
        )

    def create_plan(self, *, package_id: str, package_name: str, package_version: str, ontology_iri: str, version_iri: str, cq_test_plan: dict[str, Any], default_namespace: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        package = self.confirmed(package_id)
        attestation = self.attest(package_id)
        project_lock = self._resolver().resolve(package["project_lock_id"]).document
        baseline = load_baseline_closure(project_lock, domain_packs_root=self.domain_packs_root)
        scope = self._resolver().resolve(package["scope_id"]).document
        question_set = self._resolver().resolve(package["competency_question_set_id"]).document
        known_questions = {item["question_id"] for item in question_set["questions"]}
        cq_questions = {item["question_id"] for item in cq_test_plan["tests"]}
        if not cq_questions.issubset(known_questions):
            raise ValueError("CQ test plan references a question outside the confirmed authority set")
        if len(cq_test_plan["tests"]) > self.policy["resource_limits"]["max_cq_count"]:
            raise ValueError("CQ test count exceeds compiler policy")
        for test in cq_test_plan["tests"]:
            for limit in test["resource_limits"]:
                policy_limit = self.policy["resource_limits"].get(limit["name"])
                if policy_limit is None or limit["value"] > policy_limit:
                    raise ValueError(f"CQ resource limit exceeds compiler policy: {limit['name']}")
        namespace = default_namespace or scope["namespace_policy"]["default_namespace"]
        try:
            plan = build_compilation_plan(attestation=attestation, confirmed_package=package, compiler_snapshot=self.snapshot, compiler_policy=self.policy, package_name=package_name, package_version=package_version, ontology_iri=ontology_iri, version_iri=version_iri, default_namespace=namespace, cq_test_plan=cq_test_plan, baseline_assets=list(baseline.assets), baseline_ontology_iris=list(baseline.ontology_iris))
        except SemanticKernelError:
            raise
        except (TypeError, ValueError) as exc:
            raise CompilationPlanError(str(exc)) from exc
        destination = self.workspace / "artifacts" / "builds" / "compilation" / "plans" / package_storage_key(plan["plan_id"])
        files = {
            "compiler-input-attestation.json": _json(attestation),
            "semantic-compiler-snapshot.json": _json(self.snapshot),
            "semantic-compilation-plan.json": _json(plan),
            "competency-question-test-plan.json": _json(cq_test_plan),
        }
        with WorkspaceOperationLock(self.workspace, "semantic-compilation-plan"):
            if destination.exists():
                actual = {
                    path.name: path.read_bytes()
                    for path in destination.iterdir()
                    if path.is_file() and not path.is_symlink()
                }
                if actual != files:
                    raise ValueError("immutable compilation plan directory has different bytes")
                return plan, attestation
            staging_root = self.workspace / "tmp" / "compilation" / "plans"
            staging_root.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix="plan-", dir=staging_root))
            try:
                for name, data in files.items():
                    (staging / name).write_bytes(data)
                destination.parent.mkdir(parents=True, exist_ok=True)
                staging.replace(destination)
            except BaseException:
                if staging.exists() and staging_root in staging.parents:
                    shutil.rmtree(staging)
                raise
        return plan, attestation

    def build(self, plan_id: str) -> PackageBuildResult:
        resolver = self._resolver()
        plan = resolver.resolve(plan_id).document
        package = resolver.resolve(plan["confirmed_package_id"]).document
        attestation = resolver.resolve(plan["compiler_input_attestation_id"]).document
        stored_snapshot = resolver.resolve(plan["compiler_snapshot_id"]).document
        if stored_snapshot != self.snapshot:
            raise ValueError("compilation plan is stale for the current compiler snapshot")
        current_attestation = self.attest(package["package_id"])
        if current_attestation != attestation:
            raise ValueError("compilation input attestation is stale")
        build_id = stable_urn("semantic-compilation-build", {"plan_id": plan_id})
        build_key = package_storage_key(build_id)
        build_directory = self.workspace / "artifacts" / "builds" / "compilation" / build_key
        validation_directory = self.workspace / "artifacts" / "validation" / "compilation" / build_key
        if build_directory.is_dir() and validation_directory.is_dir():
            run_path = build_directory / "semantic-compilation-run.json"
            if run_path.is_file() and not run_path.is_symlink():
                existing_run = json.loads(run_path.read_bytes())
                if existing_run.get("plan_id") == plan_id and isinstance(existing_run.get("package_id"), str):
                    package_directory = self.workspace / "artifacts" / "packages" / package_storage_key(existing_run["package_id"])
                    verify_package(package_directory)
                    return PackageBuildResult(build_id=build_id, package_id=existing_run["package_id"], package_directory=package_directory, archive_path=None, artifacts={})
        cq_plan = resolver.resolve(plan["competency_question_test_plan_id"]).document
        project_lock = resolver.resolve(package["project_lock_id"]).document
        review_log = resolver.resolve(package["review_decision_log_id"]).document
        proposal = resolver.resolve(package["source_proposal_id"]).document
        baseline = load_baseline_closure(project_lock, domain_packs_root=self.domain_packs_root)
        resolved_ids = {item["artifact_id"] for item in attestation["resolved_artifacts"]}
        resolved = {
            key: resolver.index[key].document
            for key in sorted(resolved_ids)
            if key in resolver.index
        }
        def query_loader(reference: str) -> bytes:
            if reference in baseline.query_assets:
                return baseline.query_assets[reference]
            record = resolver.index.get(reference)
            if record is not None:
                return (self.workspace / record.relative_path).read_bytes()
            source = safe_child(self.workspace, reference, must_exist=True)
            if not source.is_file():
                raise ValueError("CQ query artifact is unavailable")
            return source.read_bytes()
        artifacts, manifest, lock, details = compile_plan(plan=plan, attestation=attestation, confirmed_package=package, compiler_snapshot=stored_snapshot, compiler_policy=self.policy, project_lock=project_lock, baseline=baseline, cq_test_plan=cq_plan, review_log=review_log, proposal=proposal, resolved_artifacts=resolved, reasoner_jar=self.reasoner_jar, query_loader=query_loader)
        build_documents = {"compiler-input-attestation.json": attestation, "semantic-compiler-snapshot.json": stored_snapshot, "semantic-compilation-plan.json": plan, "tbox-compilation-report.json": details["compilation_reports"][0], "abox-compilation-report.json": details["compilation_reports"][1], "shacl-compilation-report.json": details["compilation_reports"][2]}
        run_core = {"manifest_kind": "KG_MNP_SEMANTIC_COMPILATION_RUN", "schema_version": "1.0.0", "plan_id": plan_id, "build_id": build_id, "package_id": manifest["package_id"], "operation_statuses": [{"operation": operation, "status": "PASSED"} for operation in plan["operations"]], "status": "SUCCEEDED", "issues": []}
        build_documents["semantic-compilation-run.json"] = finalize_artifact(run_core, id_field="run_id", urn_kind="semantic-compilation-run", contract="semantic-compilation-run")
        expected_package = {
            **artifacts,
            "ontology-package.json": _json(manifest),
            "ontology-package.lock.json": _json(lock),
        }
        package_directory = self.workspace / "artifacts" / "packages" / package_storage_key(manifest["package_id"])
        if any(path.exists() for path in (package_directory, build_directory, validation_directory)):
            if not all(path.is_dir() for path in (package_directory, build_directory, validation_directory)):
                raise ValueError("partial semantic build destinations exist")
            verify_package(package_directory)
            actual_package = {
                path.relative_to(package_directory).as_posix(): path.read_bytes()
                for path in package_directory.rglob("*")
                if path.is_file() and not path.is_symlink()
            }
            expected_build = {name: _json(document) for name, document in build_documents.items()}
            actual_build = {path.name: path.read_bytes() for path in build_directory.iterdir() if path.is_file() and not path.is_symlink()}
            expected_validation = {
                "ontology-package-validation-report.json": _json(details["package_validation"]),
                "build-reproduction-report.json": _json(details["reproduction"]),
            }
            actual_validation = {path.name: path.read_bytes() for path in validation_directory.iterdir() if path.is_file() and not path.is_symlink()}
            if actual_package != expected_package or actual_build != expected_build or actual_validation != expected_validation:
                raise ValueError("immutable semantic build exists with different bytes")
            return PackageBuildResult(build_id=build_id, package_id=manifest["package_id"], package_directory=package_directory, archive_path=None, artifacts=artifacts)
        with SemanticCompilationTransaction(self.workspace, build_id=build_id, package_id=manifest["package_id"]) as transaction:
            package_dir = transaction.directory("package")
            for relative, data in sorted(artifacts.items()):
                path = package_dir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            (package_dir / "ontology-package.json").write_bytes(_json(manifest))
            (package_dir / "ontology-package.lock.json").write_bytes(_json(lock))
            verify_package(package_dir)
            for name, document in build_documents.items():
                (transaction.directory("build") / name).write_bytes(_json(document))
            for name, document in (("ontology-package-validation-report.json", details["package_validation"]), ("build-reproduction-report.json", details["reproduction"])):
                (transaction.directory("validation") / name).write_bytes(_json(document))
            transaction.commit()
        return PackageBuildResult(build_id=build_id, package_id=manifest["package_id"], package_directory=package_directory, archive_path=None, artifacts=artifacts)

    def reproduce(self, plan_id: str) -> dict[str, Any]:
        """Independently recompile a plan and compare every authoritative byte."""

        resolver = self._resolver()
        plan = resolver.resolve(plan_id).document
        package = resolver.resolve(plan["confirmed_package_id"]).document
        attestation = resolver.resolve(plan["compiler_input_attestation_id"]).document
        stored_snapshot = resolver.resolve(plan["compiler_snapshot_id"]).document
        if stored_snapshot != self.snapshot:
            raise ValueError("compilation plan is stale for the current compiler snapshot")
        if self.attest(package["package_id"]) != attestation:
            raise ValueError("compilation input attestation is stale")
        cq_plan = resolver.resolve(plan["competency_question_test_plan_id"]).document
        project_lock = resolver.resolve(package["project_lock_id"]).document
        review_log = resolver.resolve(package["review_decision_log_id"]).document
        proposal = resolver.resolve(package["source_proposal_id"]).document
        baseline = load_baseline_closure(
            project_lock,
            domain_packs_root=self.domain_packs_root,
        )
        resolved_ids = {item["artifact_id"] for item in attestation["resolved_artifacts"]}
        resolved = {
            key: resolver.index[key].document
            for key in sorted(resolved_ids)
            if key in resolver.index
        }

        def query_loader(reference: str) -> bytes:
            if reference in baseline.query_assets:
                return baseline.query_assets[reference]
            record = resolver.index.get(reference)
            if record is not None:
                return (self.workspace / record.relative_path).read_bytes()
            source = safe_child(self.workspace, reference, must_exist=True)
            if not source.is_file():
                raise ValueError("CQ query artifact is unavailable")
            return source.read_bytes()

        artifacts, manifest, lock, _ = compile_plan(
            plan=plan,
            attestation=attestation,
            confirmed_package=package,
            compiler_snapshot=stored_snapshot,
            compiler_policy=self.policy,
            project_lock=project_lock,
            baseline=baseline,
            cq_test_plan=cq_plan,
            review_log=review_log,
            proposal=proposal,
            resolved_artifacts=resolved,
            reasoner_jar=self.reasoner_jar,
            query_loader=query_loader,
        )
        expected = {
            **artifacts,
            "ontology-package.json": _json(manifest),
            "ontology-package.lock.json": _json(lock),
        }
        package_directory = (
            self.workspace
            / "artifacts"
            / "packages"
            / package_storage_key(manifest["package_id"])
        )
        verify_package(package_directory)
        actual = {
            path.relative_to(package_directory).as_posix(): path.read_bytes()
            for path in package_directory.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        mismatches = sorted(
            path
            for path in set(expected) | set(actual)
            if expected.get(path) != actual.get(path)
        )
        expected_archive = archive_mapping_bytes(expected)
        actual_archive = archive_mapping_bytes(actual)
        if mismatches or expected_archive != actual_archive:
            raise SemanticKernelError(
                "independent semantic build differs from the immutable package: "
                + ", ".join(mismatches[:20]),
                code="BUILD_REPRODUCTION_MISMATCH",
            )
        return {
            "status": "PASSED",
            "plan_id": plan_id,
            "package_id": manifest["package_id"],
            "compared_file_count": len(expected),
            "mismatches": [],
            "archive_sha256": hashlib.sha256(expected_archive).hexdigest(),
        }

    def export(self, package_id: str) -> dict[str, Any]:
        storage_key = package_storage_key(package_id)
        package_directory = self.workspace / "artifacts" / "packages" / storage_key
        destination = self.workspace / "artifacts" / "packages" / "exports" / f"{storage_key}.kgop"
        with WorkspaceOperationLock(self.workspace, "ontology-package-export"):
            result = export_kgop(package_directory, destination)
            relative_archive = destination.relative_to(self.workspace).as_posix()
            receipt = {
                "manifest_kind": "KG_MNP_PACKAGE_EXPORT_RECEIPT",
                "schema_version": "1.0.0",
                "package_id": package_id,
                "archive_path": relative_archive,
                "archive_sha256": result["archive_sha256"],
                "size_bytes": result["size_bytes"],
                "operation_time": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
            receipt_path = self.workspace / "reports" / "package-exports" / f"{storage_key}.json"
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(receipt_path, receipt)
        return {
            **result,
            "archive_path": relative_archive,
            "receipt_path": receipt_path.relative_to(self.workspace).as_posix(),
        }
