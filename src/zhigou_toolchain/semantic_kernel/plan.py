"""Deterministic, non-writing semantic compilation plans."""

from __future__ import annotations

from typing import Any

from zhigou_toolchain.contracts.identifiers import validate_semver

from .contracts import finalize_artifact, verify_artifact
from .security import validate_iri, validate_package_name
from .validation import validate_confirmed_candidates

OPERATIONS = [
    "VERIFY_INPUT", "LOAD_BASELINE", "COMPILE_TBOX", "COMPILE_ABOX", "COMPILE_SHACL", "COMPILE_MAPPING", "COMPILE_PROVENANCE", "BUILD_DATASET", "VALIDATE_RDF", "VALIDATE_OWL_PROFILE", "VALIDATE_OWL_CONSISTENCY", "VALIDATE_SHACL", "EXECUTE_CQ", "VALIDATE_PROVENANCE", "ASSEMBLE_PACKAGE", "VERIFY_PACKAGE", "EXPORT_PACKAGE",
]

GRAPH_PLAN = [
    {"role": "ontology-module", "source_partitions": ["TBOX"]},
    {"role": "effective-tbox", "source_partitions": ["BASELINE", "TBOX"]},
    {"role": "abox", "source_partitions": ["ABOX"]},
    {"role": "compiled-shapes", "source_partitions": ["SHACL"]},
    {"role": "effective-shapes", "source_partitions": ["BASELINE", "SHACL"]},
    {"role": "mapping-provenance", "source_partitions": ["MAPPING", "PROVENANCE"]},
    {"role": "statement-provenance", "source_partitions": ["PROVENANCE"]},
    {"role": "evidence-lineage", "source_partitions": ["LINEAGE"]},
    {"role": "review-audit", "source_partitions": ["AUDIT"]},
    {"role": "compilation-activity", "source_partitions": ["ACTIVITY"]},
]

EXPECTED_ARTIFACTS = [
    "ontology/module.nt", "ontology/module.ttl", "ontology/tbox-delta.nt", "ontology/tbox-delta.ttl", "ontology/effective-tbox.nt", "ontology/effective-tbox.ttl", "ontology/import-catalog.xml", "data/abox.nt", "data/abox.ttl", "shapes/compiled-shapes.nt", "shapes/compiled-shapes.ttl", "shapes/effective-shapes.nt", "shapes/effective-shapes.ttl", "mappings/mapping-plan.json", "dataset/dataset.nq", "dataset/dataset.trig", "dataset/rdf-dataset-manifest.json", "provenance/statements.nt", "provenance/statements.ttl", "provenance/review-audit.nt", "provenance/review-audit.ttl", "provenance/evidence-lineage.nt", "provenance/evidence-lineage.ttl", "provenance/statement-provenance-manifest.json", "validation/rdf-syntax-report.json", "validation/owl-profile-report.json", "validation/owl-consistency-report.json", "validation/shacl-validation-report.json", "validation/competency-question-test-plan.json", "validation/competency-question-test-report.json", "validation/provenance-closure-report.json", "validation/ontology-package-validation-report.json", "validation/build-reproduction-report.json",
]


def build_compilation_plan(
    *,
    attestation: dict[str, Any],
    confirmed_package: dict[str, Any],
    compiler_snapshot: dict[str, Any],
    compiler_policy: dict[str, Any],
    package_name: str,
    package_version: str,
    ontology_iri: str,
    version_iri: str,
    default_namespace: str,
    cq_test_plan: dict[str, Any],
    baseline_assets: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    baseline_ontology_iris: list[str] | tuple[str, ...] = (),
    language_policy: list[str] | tuple[str, ...] = ("en",),
) -> dict[str, Any]:
    if attestation["status"] != "VALID":
        raise ValueError("only a VALID compiler input attestation can produce a plan")
    validate_package_name(package_name)
    validate_semver(package_version)
    validate_iri(ontology_iri, label="ontology IRI")
    validate_iri(version_iri, label="version IRI")
    validate_iri(default_namespace, label="default namespace")
    if package_version not in version_iri:
        raise ValueError("version IRI is not bound to the explicit package version")
    verify_artifact(cq_test_plan, id_field="test_plan_id", urn_kind="competency-question-test-plan", contract="competency-question-test-plan")
    partitions = {"TBOX": confirmed_package["confirmed_tbox"], "MAPPING": confirmed_package["confirmed_mapping"], "ABOX": confirmed_package["confirmed_abox"], "SHACL": confirmed_package["confirmed_shacl"]}
    validated = validate_confirmed_candidates(partitions, supported_types=set(compiler_policy["supported_candidate_types"]))
    dispatch = []
    for value in validated:
        partition = value["partition"]
        candidate = value["candidate"]
        kind = candidate["body"]["candidate_type"]
        output_role = {"TBOX": "ontology-module", "MAPPING": "mapping-provenance", "ABOX": "abox", "SHACL": "compiled-shapes"}[partition]
        maximum = 0 if candidate["candidate_action"] in {"REUSE_EXISTING", "ALIGN_TO_EXISTING"} and partition == "TBOX" else (2 * len(candidate["body"].get("values", [])) + 2 if kind == "IN_VALUES" else 4)
        dispatch.append({"candidate_id": candidate["candidate_id"], "partition": partition, "candidate_type": kind, "candidate_action": candidate["candidate_action"], "compiler_rule_id": f"P05_{partition}_{kind}", "output_graph_role": output_role, "dependency_ids": candidate["dependency_candidate_refs"], "expected_statement_range": {"minimum": 0 if maximum == 0 else 1, "maximum": maximum}})
    ontology_identity = {"ontology_name": package_name, "ontology_iri": ontology_iri, "version_iri": version_iri, "ontology_version": package_version, "default_namespace": default_namespace, "language_policy": sorted(set(language_policy)), "baseline_ontology_iris": sorted(set(baseline_ontology_iris))}
    package_identity = {"package_name": package_name, "package_version": package_version, "package_format_version": "1.0.0", "package_profile": "PORTABLE_OFFLINE"}
    core = {"manifest_kind": "KG_MNP_SEMANTIC_COMPILATION_PLAN", "schema_version": "1.0.0", "compiler_input_attestation_id": attestation["attestation_id"], "confirmed_package_id": confirmed_package["package_id"], "compiler_snapshot_id": compiler_snapshot["snapshot_id"], "ontology_identity": ontology_identity, "package_identity": package_identity, "baseline_assets": sorted(baseline_assets, key=lambda item: (item["pack_lock_id"], item["asset_path"])), "candidate_dispatch": dispatch, "graph_plan": GRAPH_PLAN, "validation_profiles": ["RDF_ROUND_TRIP", compiler_policy["owl_profile_policy"], "PINNED_HERMIT", "SHACL_FINAL", "CQ_WITH_ORACLE", "PROVENANCE_CLOSURE", "PACKAGE_STRICT"], "competency_question_test_plan_id": cq_test_plan["test_plan_id"], "resource_limits": compiler_policy["resource_limits"], "expected_artifacts": sorted(EXPECTED_ARTIFACTS), "operations": OPERATIONS, "status": "READY", "issues": []}
    return finalize_artifact(core, id_field="plan_id", urn_kind="semantic-compilation-plan", contract="semantic-compilation-plan")
