"""Authority-gated deterministic Stage 06 compilation orchestrator."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from rdflib import URIRef

from ..modeling.dependencies import (
    ROOT,
    TERM_INVENTORY_PATH,
    verify_ontology_baseline_manifest,
)
from ..modeling.package_validation import load_term_type_index
from ..modeling.semantic_validation import validate_confirmed_modeling_package_semantics
from .abox_compiler import compile_abox
from .artifacts import write_artifact_set
from .contracts import validate_compilation_contract
from .identifiers import graph_iri
from .manifest import artifact_record, complete_manifest, json_bytes, json_semantic_hash, rdf_semantic_hash
from .owl_consistency import check_owl_consistency, load_ontology_graph
from .policy import (
    POLICY_PATH,
    compiler_policy_hash,
    load_compiler_policy,
    profile_files,
    validate_compiler_policy,
)
from .provenance_compiler import compile_modeling_provenance
from .rdf_canonical import (
    canonical_nquads,
    canonical_ntriples,
    deterministic_trig,
    deterministic_turtle,
)
from .review_audit_compiler import compile_review_audit
from .shacl_validation import validate_abox


class CompilationError(ValueError):
    pass


def validate_ready_package(
    cleaned_partial_data: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
    package: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    terminology_profile: Mapping[str, Any],
    proposal_policy: Mapping[str, Any],
    review_policy: Mapping[str, Any],
    *,
    term_types: Mapping[str, str] | None = None,
) -> None:
    validate_confirmed_modeling_package_semantics(
        package,
        proposal,
        decision_log,
        cleaned_partial_data=cleaned_partial_data,
        ontology_baseline=ontology_baseline,
        mapping_rules=mapping_rules,
        terminology_profile=terminology_profile,
        proposal_policy=proposal_policy,
        review_policy=review_policy,
        term_types=term_types if term_types is not None else load_term_type_index(),
        require_complete=True,
    )
    manifest = package.get("publication_manifest", {})
    if manifest.get("package_status") != "READY_FOR_COMPILATION":
        raise CompilationError("only READY_FOR_COMPILATION packages can be compiled")
    if manifest.get("compile_allowed") is not True:
        raise CompilationError("confirmed package compile_allowed must be true")
    if package.get("confirmed_schema_delta") != []:
        raise CompilationError("confirmed_schema_delta must be empty")


def validate_compilation_authorities(
    cleaned_partial_data: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
    package: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    terminology_profile: Mapping[str, Any],
    proposal_policy: Mapping[str, Any],
    review_policy: Mapping[str, Any],
    compiler_policy: Mapping[str, Any] | None = None,
    *,
    authority_root: Path = ROOT,
) -> dict[str, Any]:
    """Validate every compiler authority before any execution or artifact work."""

    root = authority_root.resolve()
    baseline_errors = verify_ontology_baseline_manifest(ontology_baseline, root=root)
    if baseline_errors:
        raise CompilationError(
            "ontology baseline verification failed: " + "; ".join(baseline_errors)
        )
    term_inventory = root / "docs" / "ontology" / TERM_INVENTORY_PATH.name
    term_types = load_term_type_index(term_inventory)
    validate_ready_package(
        cleaned_partial_data,
        proposal,
        decision_log,
        package,
        ontology_baseline,
        mapping_rules,
        terminology_profile,
        proposal_policy,
        review_policy,
        term_types=term_types,
    )
    policy = (
        dict(compiler_policy)
        if compiler_policy is not None
        else load_compiler_policy(root / "config" / "compilation" / POLICY_PATH.name)
    )
    validate_compiler_policy(policy)
    for profile_id in policy["shacl"]["default_profiles"]:
        profile_files(profile_id, root=root)
    return policy


def _rdf_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_artifact_set(
    cleaned_partial_data: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
    package: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    terminology_profile: Mapping[str, Any],
    proposal_policy: Mapping[str, Any],
    review_policy: Mapping[str, Any],
    compiler_policy: Mapping[str, Any] | None = None,
    *,
    authority_root: Path = ROOT,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    policy = validate_compilation_authorities(
        cleaned_partial_data,
        proposal,
        decision_log,
        package,
        ontology_baseline,
        mapping_rules,
        terminology_profile,
        proposal_policy,
        review_policy,
        compiler_policy,
        authority_root=authority_root,
    )
    package_hash = str(package["package_semantic_hash"])
    abox_graph, assertions = compile_abox(
        package,
        proposal,
        ontology_baseline,
        compilation_hash=package_hash,
        term_types=load_term_type_index(
            authority_root / "docs" / "ontology" / TERM_INVENTORY_PATH.name
        ),
    )
    provenance_graph = compile_modeling_provenance(assertions)
    review_graph = compile_review_audit(decision_log, package)
    graph_iris = {
        "business_abox": graph_iri("abox", package_hash),
        "modeling_provenance": graph_iri("modeling-provenance", package_hash),
        "review_audit": graph_iri("review-audit", package_hash),
    }

    abox_nt = canonical_ntriples(abox_graph)
    provenance_nt = canonical_ntriples(provenance_graph)
    review_nt = canonical_ntriples(review_graph)
    graphs = {
        URIRef(graph_iris["business_abox"]): abox_graph,
        URIRef(graph_iris["modeling_provenance"]): provenance_graph,
        URIRef(graph_iris["review_audit"]): review_graph,
    }
    quads = [
        (subject, predicate, obj, graph_name)
        for graph_name, graph in graphs.items()
        for subject, predicate, obj in graph
    ]
    dataset_nq = canonical_nquads(quads)
    ontology_graph = load_ontology_graph(root=authority_root)
    shacl_report, shacl_graph, profile_manifest, frozen_profiles = validate_abox(
        abox_graph, ontology_graph,
        profile_ids=tuple(policy["shacl"]["default_profiles"]),
        repository_root=authority_root,
    )
    if shacl_report["violation_count"]:
        raise CompilationError("SHACL validation reported a Violation")
    consistency = check_owl_consistency(
        abox_graph,
        ontology_baseline,
        package_hash,
        ontology_graph=ontology_graph,
        root=authority_root,
    )
    if consistency.get("status") != "CONSISTENT":
        raise CompilationError(f"OWL consistency check did not pass: {consistency.get('status')}")

    files: dict[str, bytes] = {
        "source/confirmed-modeling-package.json": json_bytes(package),
        "source/review-decision-log.json": json_bytes(decision_log),
        "rdf/abox.nt": abox_nt,
        "rdf/abox.ttl": deterministic_turtle(abox_graph),
        "rdf/modeling-provenance.nt": provenance_nt,
        "rdf/modeling-provenance.ttl": deterministic_turtle(provenance_graph),
        "rdf/review-audit.nt": review_nt,
        "rdf/review-audit.ttl": deterministic_turtle(review_graph),
        "rdf/dataset.nq": dataset_nq,
        "rdf/dataset.trig": deterministic_trig(graphs),
        "shacl/profile-manifest.json": json_bytes(profile_manifest),
        "shacl/report.json": json_bytes(shacl_report),
        "shacl/report.nt": canonical_ntriples(shacl_graph),
        "reasoner/owl-consistency-report.json": json_bytes(consistency),
    }
    for source_path, data in frozen_profiles.items():
        files[f"shacl/profiles/{Path(source_path).name}"] = data

    triple_counts = {
        "rdf/abox.nt": len(abox_graph), "rdf/abox.ttl": len(abox_graph),
        "rdf/modeling-provenance.nt": len(provenance_graph),
        "rdf/modeling-provenance.ttl": len(provenance_graph),
        "rdf/review-audit.nt": len(review_graph), "rdf/review-audit.ttl": len(review_graph),
        "shacl/report.nt": len(shacl_graph),
    }
    roles = {
        "source/confirmed-modeling-package.json": "SOURCE_PACKAGE",
        "source/review-decision-log.json": "SOURCE_REVIEW_LOG",
        "rdf/abox.nt": "CANONICAL_ABOX", "rdf/abox.ttl": "OWL_ABOX",
        "rdf/modeling-provenance.nt": "MODELING_PROVENANCE",
        "rdf/modeling-provenance.ttl": "MODELING_PROVENANCE",
        "rdf/review-audit.nt": "REVIEW_AUDIT", "rdf/review-audit.ttl": "REVIEW_AUDIT",
        "rdf/dataset.nq": "CANONICAL_DATASET", "rdf/dataset.trig": "HUMAN_READABLE_DATASET",
        "shacl/profile-manifest.json": "SHACL_PROFILE_MANIFEST",
        "shacl/report.json": "SHACL_REPORT", "shacl/report.nt": "SHACL_REPORT",
        "reasoner/owl-consistency-report.json": "OWL_CONSISTENCY_REPORT",
    }
    media_types = {
        ".json": "application/json", ".nt": "application/n-triples",
        ".ttl": "text/turtle", ".nq": "application/n-quads", ".trig": "application/trig",
    }
    records = []
    for relative, data in sorted(files.items()):
        suffix = Path(relative).suffix
        if suffix == ".json":
            semantic = json_semantic_hash(data)
        elif suffix in {".nt", ".ttl", ".nq", ".trig"} and not relative.startswith("shacl/profiles/"):
            semantic = rdf_semantic_hash(data, suffix)
        else:
            semantic = _rdf_hash(data)
        records.append(artifact_record(
            relative, roles.get(relative, "SHACL_PROFILE"), media_types[suffix], data,
            semantic_sha256=semantic,
            triple_count=triple_counts.get(relative),
            quad_count=len(quads) if relative in {"rdf/dataset.nq", "rdf/dataset.trig"} else None,
        ))

    manifest_content = {
        "contract_version": "1.0",
        "compiler_policy_id": policy["compiler_policy_id"],
        "compiler_policy_version": policy["compiler_policy_version"],
        "compiler_policy_hash": compiler_policy_hash(policy),
        "compiler_version": policy["compiler_version"],
        "source_package_id": package["package_id"],
        "source_package_semantic_hash": package_hash,
        "source_proposal_id": proposal["proposal_id"],
        "source_proposal_hash": proposal["proposal_semantic_hash"],
        "source_review_decision_log_id": decision_log["decision_log_id"],
        "source_review_decision_log_hash": decision_log["log_hash"],
        "ontology_baseline_id": ontology_baseline["baseline_id"],
        "ontology_version": ontology_baseline["ontology_version"],
        "ontology_release_source_hash": ontology_baseline["release_source_hash"],
        "graph_iris": graph_iris,
        "artifact_manifest": records,
        "asserted_fact_count": len(assertions),
        "inferred_fact_count": 0,
        "inference_materialized": False,
        "provenance_record_count": len(assertions),
        "review_record_count": len(decision_log.get("decisions", [])),
        "shacl_status": shacl_report["status"],
        "shacl_violation_count": shacl_report["violation_count"],
        "shacl_warning_count": shacl_report["warning_count"],
        "shacl_info_count": shacl_report["info_count"],
        "owl_consistency_status": consistency["status"],
        "release_status": "FORMALLY_VALIDATED",
    }
    manifest = complete_manifest(manifest_content)
    validate_compilation_contract("compilation-manifest", manifest)
    validate_compilation_contract("shacl-validation-report", shacl_report)
    validate_compilation_contract("owl-consistency-report", consistency)
    files["compilation-manifest.json"] = json_bytes(manifest)
    return files, manifest


def compile_formal_semantics(
    cleaned_partial_data: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision_log: Mapping[str, Any],
    package: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    terminology_profile: Mapping[str, Any],
    proposal_policy: Mapping[str, Any],
    review_policy: Mapping[str, Any],
    output_dir: Path,
    compiler_policy: Mapping[str, Any] | None = None,
    *,
    force: bool = False,
    authority_root: Path = ROOT,
) -> dict[str, Any]:
    files, manifest = build_artifact_set(
        cleaned_partial_data, proposal, decision_log, package, ontology_baseline,
        mapping_rules, terminology_profile, proposal_policy, review_policy,
        compiler_policy,
        authority_root=authority_root,
    )
    write_artifact_set(output_dir, files, force=force)
    return manifest
