from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import hashlib

from ..compilation.manifest import json_bytes
from ..compilation.validator import validate_compilation_package_against_authorities
from ..compilation.artifacts import write_artifact_set
from ..modeling.dependencies import ROOT, verify_ontology_baseline_manifest
from .dataset_assembler import assemble_stage06_dataset
from .forbidden_assertions import project_forbidden_business_assertions
from .contracts import validate_graphdb_contract
from .import_plan import build_import_plan
from .manifest import build_import_manifest
from .policy import load_graphdb_policy
from .query_suite import build_query_suite
from .rdf_semantics import graphdb_semantic_hash
from .repository_config import repository_config_document, repository_config_semantic_hash, render_repository_config_nt, render_repository_config_ttl
from .tbox_assembler import assemble_runtime_tbox


class GraphDBPackageError(ValueError):
    pass


def _write_closed(output_dir: Path, files: Mapping[str, bytes], *, force: bool) -> None:
    write_artifact_set(output_dir, files, force=force)


def build_graphdb_import_package(
    compilation_directory: Path,
    cleaned_partial_data: Mapping[str, Any],
    proposal: Mapping[str, Any],
    final_review_decision_log: Mapping[str, Any],
    confirmed_modeling_package: Mapping[str, Any],
    ontology_baseline: Mapping[str, Any],
    mapping_rules: Mapping[str, Any],
    terminology_profile: Mapping[str, Any],
    proposal_policy: Mapping[str, Any],
    review_policy: Mapping[str, Any],
    compiler_policy: Mapping[str, Any] | None = None,
    *,
    output_dir: Path | None = None,
    force: bool = False,
    root: Path = ROOT,
) -> dict[str, Any]:
    root = Path(root).resolve()
    policy = load_graphdb_policy(root / "config" / "graphdb" / "graphdb-runtime-1.0.0.yaml")
    baseline_errors = verify_ontology_baseline_manifest(ontology_baseline, root=root)
    if baseline_errors:
        raise GraphDBPackageError("Stage 03 baseline verification failed: " + "; ".join(baseline_errors))
    try:
        source_status = validate_compilation_package_against_authorities(
            Path(compilation_directory), cleaned_partial_data, proposal,
            final_review_decision_log, confirmed_modeling_package, ontology_baseline,
            mapping_rules, terminology_profile, proposal_policy, review_policy,
            compiler_policy, authority_root=root,
        )
    except Exception as exc:
        raise GraphDBPackageError(f"authoritative Stage 06 validation failed: {exc}") from exc
    expected_source_status = {
        "valid": True,
        "source_package_valid": True,
        "deterministic_reconstruction_match": True,
        "shacl_status": "CONFORMS",
        "owl_consistency_status": "CONSISTENT",
        "release_status": "FORMALLY_VALIDATED",
    }
    if any(source_status.get(key) != value for key, value in expected_source_status.items()):
        raise GraphDBPackageError("Stage 06 validation result is not formally validated")
    tbox = assemble_runtime_tbox(root=root, baseline=ontology_baseline)
    dataset = assemble_stage06_dataset(Path(compilation_directory), root=root)
    assembled_quads = [*tbox["quads"], *dataset["quads"]]
    assembled_data = __import__("kg_mnp_demo.compilation.rdf_canonical", fromlist=["canonical_nquads"]).canonical_nquads(assembled_quads)
    assembled_semantic_hash = graphdb_semantic_hash(assembled_quads)
    graph_counts = {str(item["graph_iri"]): sum(1 for _, _, _, graph in assembled_quads if str(graph) == str(item["graph_iri"])) for item in tbox["modules"]}
    graph_counts.update(dataset["graph_counts"])
    config_document = repository_config_document("kg-mnp-00000000000000000000", policy=policy)
    config_ttl = render_repository_config_ttl(config_document)
    config_nt = render_repository_config_nt(config_document)
    config_semantic_hash = repository_config_semantic_hash(config_document)
    forbidden_assertions = project_forbidden_business_assertions(
        proposal,
        final_review_decision_log,
        confirmed_modeling_package,
        ontology_baseline,
        root=root,
    )
    expected_tbox_versions = [
        {
            "module_code": str(item["code"]),
            "graph_iri": str(item["graph_iri"]),
            "ontology_iri": str(item["ontology_iri"]),
            "version_iri": str(item["version_iri"]),
        }
        for item in tbox["modules"]
    ]
    expected_review_audit = {
        "decision_log_id": str(final_review_decision_log["decision_log_id"]),
        "review_session_id": str(
            final_review_decision_log["review_session"]["session_id"]
        ),
        "reviewer_id": str(final_review_decision_log["reviewer"]["reviewer_id"]),
        "decisions": [
            {
                "decision_id": str(decision["decision_id"]),
                "outcome": str(decision["decision"]),
                "decided_at": str(decision["decided_at"]),
                "subject": str(decision.get("candidate_id") or decision.get("issue_id")),
            }
            for decision in sorted(
                final_review_decision_log.get("decisions", []),
                key=lambda item: str(item.get("decision_id")),
            )
        ],
    }
    query_suite = build_query_suite(
        {item["code"]: item["graph_iri"] for item in tbox["modules"]},
        tbox_modules=tbox["module_count"],
        expected_counts=graph_counts,
        stage06_graphs=dataset["manifest"]["graph_iris"],
        forbidden_triples=forbidden_assertions.triples,
        expected_tbox_versions=expected_tbox_versions,
        expected_review_audit=expected_review_audit,
    )
    # The publication hash is independent of the derived repository id.
    artifacts: dict[str, tuple[str, bytes, str | None]] = {}
    compilation_manifest_path = Path(compilation_directory) / "compilation-manifest.json"
    artifacts["source/compilation-manifest.json"] = ("SOURCE_COMPILATION_MANIFEST", compilation_manifest_path.read_bytes(), None)
    artifacts["source/graphdb-runtime-policy.yaml"] = ("GRAPHDB_RUNTIME_POLICY", (root / "config/graphdb/graphdb-runtime-1.0.0.yaml").read_bytes(), None)
    artifacts["repository/repository-config.ttl"] = ("REPOSITORY_CONFIG", config_ttl, config_semantic_hash)
    artifacts["repository/repository-config.nt"] = ("REPOSITORY_CONFIG", config_nt, config_semantic_hash)
    artifacts["import/knowledge-graph.nq"] = ("ASSEMBLED_DATASET", assembled_data, assembled_semantic_hash)
    artifacts["verification/expected/forbidden-business-assertions.nt"] = (
        "FORBIDDEN_ASSERTION_PROJECTION",
        forbidden_assertions.ntriples,
        hashlib.sha256(forbidden_assertions.ntriples).hexdigest(),
    )
    artifacts["verification/expected/forbidden-business-assertions.json"] = (
        "FORBIDDEN_ASSERTION_PROJECTION",
        json_bytes(forbidden_assertions.as_json()),
        forbidden_assertions.semantic_hash,
    )
    validate_graphdb_contract(
        "forbidden-business-assertions", forbidden_assertions.as_json()
    )
    artifacts["verification/query-suite-manifest.json"] = ("QUERY_SUITE_MANIFEST", json_bytes(query_suite), query_suite["query_suite_hash"])
    import_plan = build_import_plan(publication_id="urn:kg-mnp:graphdb-publication:" + "0" * 64, repository_id="kg-mnp-00000000000000000000", query_suite_id=query_suite["query_suite_id"])
    artifacts["import/import-plan.json"] = ("IMPORT_PLAN", json_bytes(import_plan), None)
    for name, query in sorted(query_suite["queries"].items()):
        artifacts[f"verification/queries/{name}.rq"] = ("VERIFICATION_QUERY", query.encode("utf-8"), None)
    expected_summary = {"named_graph_count": len(graph_counts), "quad_count": len(assembled_quads), "tbox_module_count": tbox["module_count"]}
    expected_counts = {"graph_counts": graph_counts, "assembled_quad_count": len(assembled_quads), "default_graph_count": 0, "blank_node_count": 0}
    artifacts["verification/expected/repository-summary.json"] = ("EXPECTED_RESULT", json_bytes(expected_summary), None)
    artifacts["verification/expected/named-graph-counts.json"] = ("EXPECTED_RESULT", json_bytes(graph_counts), None)
    artifacts["verification/expected/verification-expectations.json"] = ("EXPECTED_RESULT", json_bytes({"query_suite_id": query_suite["query_suite_id"], "query_suite_hash": query_suite["query_suite_hash"], "expectations": query_suite["expected"], "counts": expected_counts}), None)
    # Manifest artifact paths include manifest itself only after the deterministic set is known.
    manifest = build_import_manifest(policy=policy, compilation_manifest=dataset["manifest"], source_package=confirmed_modeling_package, ontology_baseline=ontology_baseline, repository_config_bytes=config_ttl, repository_config_semantic_hash=config_semantic_hash, assembled_data=assembled_data, assembled_semantic_hash=assembled_semantic_hash, query_suite=query_suite, forbidden_assertion_set_hash=forbidden_assertions.semantic_hash, forbidden_assertion_count=forbidden_assertions.statement_count, artifacts=artifacts, tbox_module_count=tbox["module_count"], tbox_triple_count=tbox["triple_count"], stage06_quad_count=dataset["quad_count"], assembled_quad_count=len(assembled_quads), named_graphs=[*tbox["named_graphs"], *dataset["named_graphs"]])
    validate_graphdb_contract("graphdb-import-manifest", manifest)
    validate_graphdb_contract("import-plan", import_plan)
    validate_graphdb_contract("query-suite-manifest", query_suite)
    repository_id = manifest["repository_id"]
    config_document = repository_config_document(repository_id, policy=policy)
    config_ttl = render_repository_config_ttl(config_document)
    config_nt = render_repository_config_nt(config_document)
    artifacts["repository/repository-config.ttl"] = ("REPOSITORY_CONFIG", config_ttl, config_semantic_hash)
    artifacts["repository/repository-config.nt"] = ("REPOSITORY_CONFIG", config_nt, config_semantic_hash)
    import_plan["publication_id"] = manifest["publication_id"]
    import_plan["repository_id"] = repository_id
    import_plan["plan_id"] = "urn:kg-mnp:graphdb-import-plan:" + manifest["publication_semantic_hash"]
    artifacts["import/import-plan.json"] = ("IMPORT_PLAN", json_bytes(import_plan), None)
    manifest = build_import_manifest(policy=policy, compilation_manifest=dataset["manifest"], source_package=confirmed_modeling_package, ontology_baseline=ontology_baseline, repository_config_bytes=config_ttl, repository_config_semantic_hash=config_semantic_hash, assembled_data=assembled_data, assembled_semantic_hash=assembled_semantic_hash, query_suite=query_suite, forbidden_assertion_set_hash=forbidden_assertions.semantic_hash, forbidden_assertion_count=forbidden_assertions.statement_count, artifacts=artifacts, tbox_module_count=tbox["module_count"], tbox_triple_count=tbox["triple_count"], stage06_quad_count=dataset["quad_count"], assembled_quad_count=len(assembled_quads), named_graphs=[*tbox["named_graphs"], *dataset["named_graphs"]])
    validate_graphdb_contract("graphdb-import-manifest", manifest)
    validate_graphdb_contract("import-plan", import_plan)
    files = {"graphdb-import-manifest.json": json_bytes(manifest)}
    files.update({path: data for path, (_, data, _) in artifacts.items()})
    if output_dir is not None:
        _write_closed(Path(output_dir), files, force=force)
    return {
        "manifest": manifest,
        "files": files,
        "source_validation": source_status,
        "tbox": tbox,
        "dataset": dataset,
        "query_suite": query_suite,
        "repository_config": config_document,
        "forbidden_assertions": forbidden_assertions,
    }


build_package = build_graphdb_import_package
