#!/usr/bin/env python3
"""Generate the additive Prompt 5 JSON Schemas.

The generator deliberately owns only the 24 new schemas.  The 59 schemas that
precede Prompt 5 are never opened for writing, which makes the migration's
byte-preservation boundary mechanically reviewable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPILATION = ROOT / "src/kg_mnp/contracts/schemas/compilation"
TOOLCHAIN = ROOT / "src/kg_mnp/contracts/schemas/toolchain"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
BASE = "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/compilation"
COMMON = f"{BASE}/compilation-common/1.0"


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _ref(name: str) -> dict[str, str]:
    return {"$ref": f"{COMMON}#/$defs/{name}"}


def _array(item: dict[str, Any], *, maximum: int = 100000, minimum: int = 0) -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": minimum,
        "maxItems": maximum,
        "items": item,
    }


def _object(properties: dict[str, Any], required: list[str] | tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(required),
    }


def _artifact(
    *,
    slug: str,
    title: str,
    kind: str,
    id_field: str,
    properties: dict[str, Any],
    required: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    base = {
        "manifest_kind": {"const": kind},
        "schema_version": {"const": "1.0.0"},
        id_field: _ref("stableId"),
        "content_digest": _ref("sha256"),
    }
    return {
        "$schema": DRAFT,
        "$id": f"{BASE}/{slug}/1.0",
        "title": title,
        **_object(
            {**base, **properties},
            ["manifest_kind", "schema_version", id_field, *required, "content_digest"],
        ),
    }


def _common() -> dict[str, Any]:
    safe_text = {"type": "string", "minLength": 1, "maxLength": 16384}
    stable_id = {
        "type": "string",
        "minLength": 1,
        "maxLength": 256,
        "pattern": r"^urn:kg-mnp:[a-z0-9-]+:[0-9a-f]{64}$",
    }
    iri = {
        "type": "string",
        "minLength": 1,
        "maxLength": 2048,
        "pattern": r"^(?:https://|urn:|http://(?:www\.w3\.org|purl\.org)/)[^\s<>\"{}|\\^`]+$",
    }
    path = {
        "type": "string",
        "minLength": 1,
        "maxLength": 512,
        "pattern": r"^(?!/)(?![A-Za-z]:)(?!\\\\)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9._/-]+$",
    }
    issue = _object(
        {
            "issue_id": stable_id,
            "code": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 128},
            "severity": {"enum": ["INFO", "WARNING", "BLOCKING"]},
            "message": {"type": "string", "minLength": 1, "maxLength": 4096},
            "artifact_refs": _array(stable_id, maximum=10000),
        },
        ["issue_id", "code", "severity", "message", "artifact_refs"],
    )
    file_record = _object(
        {
            "path": path,
            "media_type": {"type": "string", "minLength": 1, "maxLength": 128},
            "size_bytes": {"type": "integer", "minimum": 0, "maximum": 1073741824},
            "byte_sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
            "semantic_sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
            "role": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 128},
        },
        ["path", "media_type", "size_bytes", "byte_sha256", "semantic_sha256", "role"],
    )
    identity = _object(
        {
            "ontology_name": {"type": "string", "pattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$", "maxLength": 128},
            "ontology_iri": iri,
            "version_iri": iri,
            "ontology_version": {"type": "string", "pattern": r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$", "maxLength": 64},
            "default_namespace": iri,
            "language_policy": _array({"type": "string", "pattern": r"^[A-Za-z0-9-]+$", "maxLength": 35}, maximum=32),
            "baseline_ontology_iris": _array(iri, maximum=32),
        },
        ["ontology_name", "ontology_iri", "version_iri", "ontology_version", "default_namespace", "language_policy", "baseline_ontology_iris"],
    )
    package_identity = _object(
        {
            "package_name": {"type": "string", "pattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$", "maxLength": 128},
            "package_version": {"type": "string", "pattern": r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$", "maxLength": 64},
            "package_format_version": {"const": "1.0.0"},
            "package_profile": {"const": "PORTABLE_OFFLINE"},
        },
        ["package_name", "package_version", "package_format_version", "package_profile"],
    )
    resource_limit = _object(
        {
            "name": {"type": "string", "pattern": r"^max_[a-z0-9_]+$", "maxLength": 128},
            "value": {"type": "integer", "minimum": 1, "maximum": 1073741824},
        },
        ["name", "value"],
    )
    return {
        "$schema": DRAFT,
        "$id": COMMON,
        "title": "KG-MNP Compilation Common Definitions 1.0",
        "type": "object",
        "additionalProperties": False,
        "properties": {},
        "$defs": {
            "sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
            "stableId": stable_id,
            "iri": iri,
            "safePath": path,
            "safeText": safe_text,
            "issue": issue,
            "fileRecord": file_record,
            "ontologyIdentity": identity,
            "packageIdentity": package_identity,
            "resourceLimit": resource_limit,
            "stableIds": {**_array(stable_id), "uniqueItems": True},
            "iris": {**_array(iri), "uniqueItems": True},
            "safePaths": {**_array(path), "uniqueItems": True},
        },
    }


def _schemas() -> dict[str, dict[str, Any]]:
    issue_list = _array(_ref("issue"), maximum=10000)
    id_list = {**_array(_ref("stableId"), maximum=100000), "uniqueItems": True}
    path_list = {**_array(_ref("safePath"), maximum=10000), "uniqueItems": True}
    counts = _object(
        {"TBOX": {"type": "integer", "minimum": 0}, "MAPPING": {"type": "integer", "minimum": 0}, "ABOX": {"type": "integer", "minimum": 0}, "SHACL": {"type": "integer", "minimum": 0}},
        ["TBOX", "MAPPING", "ABOX", "SHACL"],
    )
    validation_ref = _object(
        {"report_id": _ref("stableId"), "status": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 64}, "content_digest": _ref("sha256")},
        ["report_id", "status", "content_digest"],
    )
    schemas: dict[str, dict[str, Any]] = {"compilation_common.schema.json": _common()}

    limit_names = [
        "max_confirmed_items", "max_tbox_statements", "max_abox_statements", "max_shacl_statements", "max_mapping_rules", "max_provenance_statements", "max_dataset_quads", "max_rdf_bytes_per_file", "max_package_files", "max_package_uncompressed_bytes", "max_archive_compression_ratio", "max_reasoner_input_triples", "max_reasoner_seconds", "max_reasoner_output_bytes", "max_shacl_results", "max_shacl_seconds", "max_cq_count", "max_query_characters", "max_query_results", "max_query_seconds", "max_query_path_depth",
    ]
    limits = _object({name: {"type": "integer", "minimum": 1, "maximum": 1073741824} for name in limit_names}, limit_names)
    schemas["semantic_compiler_policy.schema.json"] = _artifact(
        slug="semantic-compiler-policy", title="KG-MNP Semantic Compiler Policy 1.0", kind="KG_MNP_SEMANTIC_COMPILER_POLICY", id_field="policy_id",
        properties={
            "policy_version": {"const": "1.0.0"}, "compiler_version": {"const": "0.5.0"},
            "input_contract": {"const": "ontology-confirmed-modeling-package/1.0.0"},
            "canonicalization_profile": {"const": "KG-MNP RDF Canonical Profile v1"},
            "skolemization_profile": {"const": "KG-MNP Structural Skolem Profile v1"},
            "package_profile": {"const": "PORTABLE_OFFLINE"}, "ontology_module_policy": {"const": "OVERLAY_MODULE"},
            "supported_candidate_types": {**_array({"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 64}, maximum=64, minimum=1), "uniqueItems": True},
            "output_formats": {**_array({"enum": ["NT", "TTL", "NQ", "TRIG", "JSON", "XML", "KGOP"]}, maximum=16, minimum=1), "uniqueItems": True},
            "named_graph_policy": {"const": "ROLE_AND_SEMANTIC_DIGEST"}, "baseline_policy": {"const": "LOCAL_LOCKED_CLOSURE"},
            "mapping_policy": {"const": "DECLARATIVE_ONLY"}, "provenance_policy": {"const": "STATEMENT_LEVEL_CLOSED"},
            "owl_profile_policy": {"enum": ["OWL_2_DL_STRICT", "OWL_RL_STRUCTURAL"]}, "owl_consistency_policy": {"const": "PINNED_HERMIT"},
            "shacl_policy": {"const": "OFFLINE_CORE_ONLY"}, "competency_question_policy": {"const": "REGISTERED_READ_ONLY_WITH_ORACLE"},
            "package_validation_policy": {"const": "STRICT_CLOSED_SET"}, "resource_limits": limits,
            "prohibited_operations": {**_array({"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 64}, maximum=64, minimum=1), "uniqueItems": True},
        },
        required=["policy_version", "compiler_version", "input_contract", "canonicalization_profile", "skolemization_profile", "package_profile", "ontology_module_policy", "supported_candidate_types", "output_formats", "named_graph_policy", "baseline_policy", "mapping_policy", "provenance_policy", "owl_profile_policy", "owl_consistency_policy", "shacl_policy", "competency_question_policy", "package_validation_policy", "resource_limits", "prohibited_operations"],
    )
    reasoner_bundle = _object(
        {"engine": {"const": "HermiT"}, "robot_version": {"const": "1.9.7"}, "robot_jar_sha256": _ref("sha256"), "hermit_version": {"const": "1.4.5.456"}, "java_requirement": {"type": "string", "pattern": r"^Java [0-9]+\+$", "maxLength": 32}, "availability": {"enum": ["AVAILABLE", "UNAVAILABLE"]}, "validation_profile": {"enum": ["OWL_2_DL_STRICT", "OWL_RL_STRUCTURAL"]}},
        ["engine", "robot_version", "robot_jar_sha256", "hermit_version", "java_requirement", "availability", "validation_profile"],
    )
    dependency = _object({"name": {"type": "string", "pattern": r"^[A-Za-z0-9_.-]+$", "maxLength": 64}, "version": {"type": "string", "minLength": 1, "maxLength": 64}}, ["name", "version"])
    implementation_file = _object({"path": _ref("safePath"), "sha256": _ref("sha256")}, ["path", "sha256"])
    schemas["semantic_compiler_snapshot.schema.json"] = _artifact(
        slug="semantic-compiler-snapshot", title="KG-MNP Semantic Compiler Snapshot 1.0", kind="KG_MNP_SEMANTIC_COMPILER_SNAPSHOT", id_field="snapshot_id",
        properties={"compiler_id": _ref("stableId"), "compiler_version": {"const": "0.5.0"}, "toolchain_version": {"const": "0.5.0"}, "policy_id": _ref("stableId"), "policy_semantic_sha256": _ref("sha256"), "canonicalization_profile": {"const": "KG-MNP RDF Canonical Profile v1"}, "skolemization_profile": {"const": "KG-MNP Structural Skolem Profile v1"}, "implementation_files": _array(implementation_file, maximum=128, minimum=1), "implementation_digest": _ref("sha256"), "python_version": {"type": "string", "pattern": r"^[0-9]+\.[0-9]+\.[0-9]+$", "maxLength": 32}, "dependency_versions": _array(dependency, maximum=32, minimum=5), "reasoner_bundle": reasoner_bundle, "validation_engines": _array(dependency, maximum=32, minimum=1)},
        required=["compiler_id", "compiler_version", "toolchain_version", "policy_id", "policy_semantic_sha256", "canonicalization_profile", "skolemization_profile", "implementation_files", "implementation_digest", "python_version", "dependency_versions", "reasoner_bundle", "validation_engines"],
    )
    resolved_artifact = _object({"artifact_id": _ref("stableId"), "path": _ref("safePath"), "byte_sha256": _ref("sha256"), "content_digest": _ref("sha256")}, ["artifact_id", "path", "byte_sha256", "content_digest"])
    schemas["compiler_input_attestation.schema.json"] = _artifact(
        slug="compiler-input-attestation", title="KG-MNP Compiler Input Attestation 1.0", kind="KG_MNP_COMPILER_INPUT_ATTESTATION", id_field="attestation_id",
        properties={"confirmed_package_id": _ref("stableId"), "confirmed_package_sha256": _ref("sha256"), "confirmed_package_semantic_digest": _ref("sha256"), "project_lock_id": _ref("stableId"), "contract_catalog_digest": _ref("sha256"), "domain_pack_lock_ids": id_list, "scope_id": _ref("stableId"), "scope_approval_id": _ref("stableId"), "competency_question_set_id": _ref("stableId"), "coverage_report_id": _ref("stableId"), "kg_ir_dataset_ids": id_list, "baseline_snapshot_id": _ref("stableId"), "term_inventory_id": _ref("stableId"), "term_alignment_set_id": _ref("stableId"), "field_mapping_candidate_set_id": _ref("stableId"), "proposal_id": _ref("stableId"), "prevalidation_report_id": _ref("stableId"), "review_policy_id": _ref("stableId"), "review_decision_log_id": _ref("stableId"), "review_semantic_hash": _ref("sha256"), "resolved_artifacts": _array(resolved_artifact, maximum=100000, minimum=1), "partition_counts": counts, "closure_results": _object({"evidence_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000}, "dependency_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000}}, ["evidence_basis_points", "dependency_basis_points"]), "status": {"enum": ["VALID", "INVALID", "STALE"]}, "issues": issue_list},
        required=["confirmed_package_id", "confirmed_package_sha256", "confirmed_package_semantic_digest", "project_lock_id", "contract_catalog_digest", "domain_pack_lock_ids", "scope_id", "scope_approval_id", "competency_question_set_id", "coverage_report_id", "kg_ir_dataset_ids", "baseline_snapshot_id", "term_inventory_id", "term_alignment_set_id", "field_mapping_candidate_set_id", "proposal_id", "prevalidation_report_id", "review_policy_id", "review_decision_log_id", "review_semantic_hash", "resolved_artifacts", "partition_counts", "closure_results", "status", "issues"],
    )
    dispatch = _object({"candidate_id": _ref("stableId"), "partition": {"enum": ["TBOX", "MAPPING", "ABOX", "SHACL"]}, "candidate_type": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 64}, "candidate_action": {"enum": ["REUSE_EXISTING", "CREATE_NEW", "ALIGN_TO_EXISTING", "ASSERT", "CONSTRAIN"]}, "compiler_rule_id": {"type": "string", "pattern": r"^P05_[A-Z0-9_]+$", "maxLength": 128}, "output_graph_role": {"type": "string", "pattern": r"^[a-z]+(?:-[a-z]+)*$", "maxLength": 64}, "dependency_ids": id_list, "expected_statement_range": _object({"minimum": {"type": "integer", "minimum": 0}, "maximum": {"type": "integer", "minimum": 0}}, ["minimum", "maximum"])}, ["candidate_id", "partition", "candidate_type", "candidate_action", "compiler_rule_id", "output_graph_role", "dependency_ids", "expected_statement_range"])
    baseline_asset = _object({"pack_lock_id": _ref("stableId"), "asset_path": _ref("safePath"), "byte_sha256": _ref("sha256"), "semantic_sha256": _ref("sha256"), "role": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 64}}, ["pack_lock_id", "asset_path", "byte_sha256", "semantic_sha256", "role"])
    graph_plan = _object({"role": {"type": "string", "pattern": r"^[a-z]+(?:-[a-z]+)*$", "maxLength": 64}, "source_partitions": _array({"enum": ["TBOX", "MAPPING", "ABOX", "SHACL", "BASELINE", "PROVENANCE", "AUDIT", "LINEAGE", "ACTIVITY"]}, maximum=16, minimum=1)}, ["role", "source_partitions"])
    schemas["semantic_compilation_plan.schema.json"] = _artifact(
        slug="semantic-compilation-plan", title="KG-MNP Semantic Compilation Plan 1.0", kind="KG_MNP_SEMANTIC_COMPILATION_PLAN", id_field="plan_id",
        properties={"compiler_input_attestation_id": _ref("stableId"), "confirmed_package_id": _ref("stableId"), "compiler_snapshot_id": _ref("stableId"), "ontology_identity": _ref("ontologyIdentity"), "package_identity": _ref("packageIdentity"), "baseline_assets": _array(baseline_asset, maximum=10000), "candidate_dispatch": _array(dispatch, maximum=100000), "graph_plan": _array(graph_plan, maximum=32, minimum=1), "validation_profiles": _array({"enum": ["RDF_ROUND_TRIP", "OWL_2_DL_STRICT", "OWL_RL_STRUCTURAL", "PINNED_HERMIT", "SHACL_FINAL", "CQ_WITH_ORACLE", "PROVENANCE_CLOSURE", "PACKAGE_STRICT"]}, maximum=16, minimum=1), "competency_question_test_plan_id": _ref("stableId"), "resource_limits": limits, "expected_artifacts": path_list, "operations": _array({"enum": ["VERIFY_INPUT", "LOAD_BASELINE", "COMPILE_TBOX", "COMPILE_ABOX", "COMPILE_SHACL", "COMPILE_MAPPING", "COMPILE_PROVENANCE", "BUILD_DATASET", "VALIDATE_RDF", "VALIDATE_OWL_PROFILE", "VALIDATE_OWL_CONSISTENCY", "VALIDATE_SHACL", "EXECUTE_CQ", "VALIDATE_PROVENANCE", "ASSEMBLE_PACKAGE", "VERIFY_PACKAGE", "EXPORT_PACKAGE"]}, maximum=32, minimum=17), "status": {"enum": ["READY", "INVALID"]}, "issues": issue_list},
        required=["compiler_input_attestation_id", "confirmed_package_id", "compiler_snapshot_id", "ontology_identity", "package_identity", "baseline_assets", "candidate_dispatch", "graph_plan", "validation_profiles", "competency_question_test_plan_id", "resource_limits", "expected_artifacts", "operations", "status", "issues"],
    )
    schemas["semantic_compilation_run.schema.json"] = _artifact(
        slug="semantic-compilation-run", title="KG-MNP Semantic Compilation Run 1.0", kind="KG_MNP_SEMANTIC_COMPILATION_RUN", id_field="run_id",
        properties={"plan_id": _ref("stableId"), "build_id": _ref("stableId"), "package_id": {"oneOf": [_ref("stableId"), {"type": "null"}]}, "operation_statuses": _array(_object({"operation": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 64}, "status": {"enum": ["PASSED", "FAILED", "NOT_RUN"]}}, ["operation", "status"]), maximum=32), "status": {"enum": ["SUCCEEDED", "FAILED"]}, "issues": issue_list},
        required=["plan_id", "build_id", "package_id", "operation_statuses", "status", "issues"],
    )
    output_iris = {**_array(_ref("iri"), maximum=100000), "uniqueItems": True}
    compilation_item = _object({"confirmed_item_id": _ref("stableId"), "candidate_type": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 64}, "output_ids": output_iris, "statement_count": {"type": "integer", "minimum": 0}}, ["confirmed_item_id", "candidate_type", "output_ids", "statement_count"])
    for filename, slug, title, kind, id_field, partition in (
        ("tbox_compilation_report.schema.json", "tbox-compilation-report", "TBox Compilation Report", "KG_MNP_TBOX_COMPILATION_REPORT", "report_id", "TBOX"),
        ("abox_compilation_report.schema.json", "abox-compilation-report", "ABox Compilation Report", "KG_MNP_ABOX_COMPILATION_REPORT", "report_id", "ABOX"),
        ("shacl_compilation_report.schema.json", "shacl-compilation-report", "SHACL Compilation Report", "KG_MNP_SHACL_COMPILATION_REPORT", "report_id", "SHACL"),
    ):
        properties = {"plan_id": _ref("stableId"), "partition": {"const": partition}, "items": _array(compilation_item, maximum=100000), "statement_count": {"type": "integer", "minimum": 0}, "semantic_sha256": _ref("sha256"), "output_files": path_list, "status": {"enum": ["PASSED", "FAILED"]}, "issues": issue_list}
        required = ["plan_id", "partition", "items", "statement_count", "semantic_sha256", "output_files", "status", "issues"]
        if partition == "SHACL":
            properties.update({"baseline_statement_count": {"type": "integer", "minimum": 0}, "effective_statement_count": {"type": "integer", "minimum": 0}, "excluded_baseline_statement_count": {"type": "integer", "minimum": 0}, "baseline_projection": {"const": "SAFE_SHACL_CORE_PROJECTION"}})
            required.extend(["baseline_statement_count", "effective_statement_count", "excluded_baseline_statement_count", "baseline_projection"])
        schemas[filename] = _artifact(slug=slug, title=f"KG-MNP {title} 1.0", kind=kind, id_field=id_field, properties=properties, required=required)
    mapping_item = _object({"compiled_mapping_id": _ref("stableId"), "source_confirmed_item_id": _ref("stableId"), "mapping_kind": {"enum": ["RECORD_TO_CLASS", "FIELD_TO_DATA_PROPERTY", "REFERENCE_TO_OBJECT_PROPERTY", "VALUE_MAPPING", "IRI_TEMPLATE", "NULL_HANDLING_POLICY"]}, "source_kgir_item_refs": id_list, "source_evidence_refs": id_list, "target_class_iri": {"oneOf": [_ref("iri"), {"type": "null"}]}, "target_property_iri": {"oneOf": [_ref("iri"), {"type": "null"}]}, "conversion_policy": {"enum": ["IDENTITY", "TRIM", "NFC", "LOWERCASE", "UPPERCASE", "CONTROLLED_LOOKUP", "NONE"]}, "null_policy": {"enum": ["REJECT", "OMIT", "PRESERVE", "CONTROLLED_DEFAULT", "NONE"]}, "value_map": _array(_object({"source": {"type": "string", "maxLength": 4096}, "target": {"type": "string", "maxLength": 4096}}, ["source", "target"]), maximum=1024), "iri_template": {"oneOf": [{"type": "string", "pattern": r"^(?:https://|urn:)[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%{}-]+$", "maxLength": 2048}, {"type": "null"}]}, "dependencies": id_list, "review_decision_ref": _ref("stableId"), "provenance_ref": _ref("stableId")}, ["compiled_mapping_id", "source_confirmed_item_id", "mapping_kind", "source_kgir_item_refs", "source_evidence_refs", "target_class_iri", "target_property_iri", "conversion_policy", "null_policy", "value_map", "iri_template", "dependencies", "review_decision_ref", "provenance_ref"])
    schemas["mapping_plan.schema.json"] = _artifact(slug="mapping-plan", title="KG-MNP Declarative Mapping Plan 1.0", kind="KG_MNP_MAPPING_PLAN", id_field="mapping_plan_id", properties={"source_plan_id": _ref("stableId"), "execution_policy": {"const": "DECLARATIVE_NOT_EXECUTED"}, "mappings": _array(mapping_item, maximum=100000), "mapping_count": {"type": "integer", "minimum": 0}}, required=["source_plan_id", "execution_policy", "mappings", "mapping_count"])
    nullable_id = {"oneOf": [_ref("stableId"), {"type": "null"}]}
    nullable_sha256 = {"oneOf": [_ref("sha256"), {"type": "null"}]}
    statement = _object(
        {
            "statement_id": _ref("stableId"),
            "subject": _ref("safeText"),
            "predicate": _ref("iri"),
            "object": _ref("safeText"),
            "graph_iri": _ref("iri"),
            "confirmed_item_id": nullable_id,
            "source_candidate_id": nullable_id,
            "review_decision_id": nullable_id,
            "review_semantic_hash": nullable_sha256,
            "provider_snapshot_refs": id_list,
            "kg_ir_item_refs": id_list,
            "evidence_record_refs": id_list,
            "source_asset_refs": id_list,
            "domain_pack_asset_refs": path_list,
            "compilation_activity_id": _ref("stableId"),
            "compiler_snapshot_id": _ref("stableId"),
            "provenance_class": {"enum": ["GENERATED", "BASELINE_REUSED"]},
        },
        [
            "statement_id", "subject", "predicate", "object", "graph_iri",
            "confirmed_item_id", "source_candidate_id", "review_decision_id",
            "review_semantic_hash", "provider_snapshot_refs", "kg_ir_item_refs",
            "evidence_record_refs", "source_asset_refs", "domain_pack_asset_refs",
            "compilation_activity_id", "compiler_snapshot_id", "provenance_class",
        ],
    )
    schemas["statement_provenance_manifest.schema.json"] = _artifact(slug="statement-provenance-manifest", title="KG-MNP Statement Provenance Manifest 1.0", kind="KG_MNP_STATEMENT_PROVENANCE_MANIFEST", id_field="provenance_manifest_id", properties={"plan_id": _ref("stableId"), "statements": _array(statement, maximum=1000000), "statement_count": {"type": "integer", "minimum": 0}, "graph_semantic_sha256": _ref("sha256")}, required=["plan_id", "statements", "statement_count", "graph_semantic_sha256"])
    graph_record = _object({"role": {"type": "string", "pattern": r"^[a-z]+(?:-[a-z]+)*$", "maxLength": 64}, "graph_iri": _ref("iri"), "triple_count": {"type": "integer", "minimum": 0}, "graph_semantic_digest": _ref("sha256"), "source_confirmed_item_count": {"type": "integer", "minimum": 0}, "provenance_coverage_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000}}, ["role", "graph_iri", "triple_count", "graph_semantic_digest", "source_confirmed_item_count", "provenance_coverage_basis_points"])
    schemas["rdf_dataset_manifest.schema.json"] = _artifact(slug="rdf-dataset-manifest", title="KG-MNP RDF Dataset Manifest 1.0", kind="KG_MNP_RDF_DATASET_MANIFEST", id_field="dataset_id", properties={"graphs": _array(graph_record, maximum=32, minimum=1), "total_quad_count": {"type": "integer", "minimum": 0}, "dataset_semantic_digest": _ref("sha256")}, required=["graphs", "total_quad_count", "dataset_semantic_digest"])
    rdf_file = _object({"path": _ref("safePath"), "media_type": {"type": "string", "minLength": 1, "maxLength": 128}, "byte_sha256": _ref("sha256"), "parsed_statement_count": {"type": "integer", "minimum": 0}, "canonical_semantic_digest": _ref("sha256"), "blank_node_count": {"type": "integer", "minimum": 0}, "parse_status": {"enum": ["PASSED", "FAILED"]}, "round_trip_status": {"enum": ["PASSED", "FAILED"]}, "equivalent_canonical_artifact": _ref("safePath")}, ["path", "media_type", "byte_sha256", "parsed_statement_count", "canonical_semantic_digest", "blank_node_count", "parse_status", "round_trip_status", "equivalent_canonical_artifact"])
    schemas["rdf_syntax_validation_report.schema.json"] = _artifact(slug="rdf-syntax-validation-report", title="KG-MNP RDF Syntax Validation Report 1.0", kind="KG_MNP_RDF_SYNTAX_VALIDATION_REPORT", id_field="report_id", properties={"dataset_id": _ref("stableId"), "files": _array(rdf_file, maximum=10000), "status": {"enum": ["PASSED", "FAILED"]}, "issues": issue_list}, required=["dataset_id", "files", "status", "issues"])
    schemas["owl_profile_report.schema.json"] = _artifact(slug="owl-profile-report", title="KG-MNP OWL Profile Report 1.0", kind="KG_MNP_OWL_PROFILE_REPORT", id_field="report_id", properties={"requested_profile": {"enum": ["OWL_2_DL_STRICT", "OWL_RL_STRUCTURAL"]}, "detected_constructs": {**_array({"type": "string", "maxLength": 128}, maximum=1024), "uniqueItems": True}, "unsupported_constructs": {**_array({"type": "string", "maxLength": 128}, maximum=1024), "uniqueItems": True}, "profile_violations": issue_list, "input_graph_digest": _ref("sha256"), "baseline_digest": _ref("sha256"), "delta_digest": _ref("sha256"), "status": {"enum": ["PASSED", "FAILED", "NOT_RUN_EXTERNAL_PREREQUISITE"]}, "validator_identity": {"type": "string", "minLength": 1, "maxLength": 128}, "validator_version": {"type": "string", "minLength": 1, "maxLength": 64}}, required=["requested_profile", "detected_constructs", "unsupported_constructs", "profile_violations", "input_graph_digest", "baseline_digest", "delta_digest", "status", "validator_identity", "validator_version"])
    schemas["semantic_owl_consistency_report.schema.json"] = _artifact(slug="semantic-owl-consistency-report", title="KG-MNP OWL Consistency Report 1.0", kind="KG_MNP_SEMANTIC_OWL_CONSISTENCY_REPORT", id_field="report_id", properties={"status": {"enum": ["CONSISTENT", "INCONSISTENT", "UNSUPPORTED_PROFILE", "REASONER_UNAVAILABLE", "TIMEOUT", "FAILED"]}, "consistent": {"type": "boolean"}, "reasoning_scope": {"const": "LOCAL_BASELINE_TBOX_ABOX_CLOSURE"}, "reasoner": {"const": "HermiT"}, "reasoner_version": {"const": "1.4.5.456"}, "robot_version": {"const": "1.9.7"}, "robot_jar_sha256": _ref("sha256"), "java_runtime_major_version": {"oneOf": [{"type": "integer", "minimum": 11, "maximum": 99}, {"type": "null"}]}, "ontology_profile": {"enum": ["OWL_2_DL_STRICT", "OWL_RL_STRUCTURAL"]}, "input_semantic_digest": _ref("sha256"), "baseline_semantic_digest": _ref("sha256"), "tbox_semantic_digest": _ref("sha256"), "abox_semantic_digest": _ref("sha256"), "exit_code": {"oneOf": [{"type": "integer", "minimum": -1, "maximum": 255}, {"type": "null"}]}, "timeout": {"type": "boolean"}, "sanitized_diagnostics_hash": _ref("sha256")}, required=["status", "consistent", "reasoning_scope", "reasoner", "reasoner_version", "robot_version", "robot_jar_sha256", "java_runtime_major_version", "ontology_profile", "input_semantic_digest", "baseline_semantic_digest", "tbox_semantic_digest", "abox_semantic_digest", "exit_code", "timeout", "sanitized_diagnostics_hash"])
    shacl_result = _object({"result_id": _ref("stableId"), "severity": {"enum": ["VIOLATION", "WARNING", "INFO"]}, "focus_node": {"oneOf": [_ref("iri"), {"type": "null"}]}, "source_shape": {"oneOf": [_ref("iri"), {"type": "null"}]}, "message": {"type": "string", "maxLength": 4096}}, ["result_id", "severity", "focus_node", "source_shape", "message"])
    schemas["semantic_shacl_validation_report.schema.json"] = _artifact(slug="semantic-shacl-validation-report", title="KG-MNP Semantic SHACL Validation Report 1.0", kind="KG_MNP_SEMANTIC_SHACL_VALIDATION_REPORT", id_field="report_id", properties={"conforms": {"type": "boolean"}, "status": {"enum": ["CONFORMS", "VIOLATION", "ENGINE_ERROR", "TIMEOUT"]}, "results": _array(shacl_result, maximum=100000), "violation_count": {"type": "integer", "minimum": 0}, "warning_count": {"type": "integer", "minimum": 0}, "info_count": {"type": "integer", "minimum": 0}, "shape_graph_digest": _ref("sha256"), "data_graph_digest": _ref("sha256"), "ontology_graph_digest": _ref("sha256"), "pyshacl_version": {"type": "string", "minLength": 1, "maxLength": 64}, "inference_profile": {"enum": ["NONE", "RDFS", "OWL_RL"]}, "meta_shacl_status": {"enum": ["PASSED", "FAILED", "NOT_RUN_UNSUPPORTED"]}, "execution_limits": _array(_ref("resourceLimit"), maximum=32, minimum=1)}, required=["conforms", "status", "results", "violation_count", "warning_count", "info_count", "shape_graph_digest", "data_graph_digest", "ontology_graph_digest", "pyshacl_version", "inference_profile", "meta_shacl_status", "execution_limits"])
    assertion = _object({"assertion_type": {"enum": ["BOOLEAN_EQUALS", "MIN_ROW_COUNT", "MAX_ROW_COUNT", "REQUIRED_BINDINGS", "REQUIRED_IRIS", "RESULT_SEMANTIC_HASH", "GRAPH_PATTERN_PRESENT"]}, "boolean_value": {"oneOf": [{"type": "boolean"}, {"type": "null"}]}, "integer_value": {"oneOf": [{"type": "integer", "minimum": 0}, {"type": "null"}]}, "string_values": {**_array({"type": "string", "maxLength": 2048}, maximum=10000), "uniqueItems": True}, "semantic_hash": {"oneOf": [_ref("sha256"), {"type": "null"}]}}, ["assertion_type", "boolean_value", "integer_value", "string_values", "semantic_hash"])
    cq_test = _object({"test_id": _ref("stableId"), "question_id": _ref("stableId"), "requirement": {"enum": ["REQUIRED", "IMPORTANT", "OPTIONAL"]}, "query_artifact_ref": {"oneOf": [_ref("stableId"), _ref("safePath")]}, "query_sha256": _ref("sha256"), "query_type": {"enum": ["ASK", "SELECT", "CONSTRUCT"]}, "target_graph_roles": _array({"type": "string", "pattern": r"^[a-z]+(?:-[a-z]+)*$", "maxLength": 64}, maximum=32, minimum=1), "expected_answer_shape": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 128}, "assertions": _array(assertion, maximum=128), "resource_limits": _array(_ref("resourceLimit"), maximum=32, minimum=1), "content_digest": _ref("sha256")}, ["test_id", "question_id", "requirement", "query_artifact_ref", "query_sha256", "query_type", "target_graph_roles", "expected_answer_shape", "assertions", "resource_limits", "content_digest"])
    schemas["competency_question_test_plan.schema.json"] = _artifact(slug="competency-question-test-plan", title="KG-MNP Competency Question Test Plan 1.0", kind="KG_MNP_COMPETENCY_QUESTION_TEST_PLAN", id_field="test_plan_id", properties={"tests": _array(cq_test, maximum=10000), "required_question_ids": id_list, "important_policy": {"enum": ["MUST_PASS", "MAY_BE_UNVERIFIED"]}, "optional_policy": {"const": "MAY_BE_UNVERIFIED"}}, required=["tests", "required_question_ids", "important_policy", "optional_policy"])
    cq_result = _object({"test_id": _ref("stableId"), "question_id": _ref("stableId"), "test_status": {"enum": ["ASSERTION_PASSED", "ASSERTION_FAILED", "EXECUTED_NO_ORACLE", "NOT_EXECUTABLE", "QUERY_REJECTED", "TIMEOUT", "ENGINE_FAILED"]}, "question_status": {"enum": ["PASSED", "FAILED", "UNVERIFIED"]}, "result_count": {"type": "integer", "minimum": 0}, "result_semantic_hash": _ref("sha256"), "assertion_results": _array(_object({"assertion_type": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 64}, "passed": {"type": "boolean"}}, ["assertion_type", "passed"]), maximum=128)}, ["test_id", "question_id", "test_status", "question_status", "result_count", "result_semantic_hash", "assertion_results"])
    schemas["competency_question_test_report.schema.json"] = _artifact(slug="competency-question-test-report", title="KG-MNP Competency Question Test Report 1.0", kind="KG_MNP_COMPETENCY_QUESTION_TEST_REPORT", id_field="report_id", properties={"test_plan_id": _ref("stableId"), "results": _array(cq_result, maximum=10000), "required_passed": {"type": "boolean"}, "status": {"enum": ["PASSED", "FAILED", "UNVERIFIED"]}, "issues": issue_list}, required=["test_plan_id", "results", "required_passed", "status", "issues"])
    missing_link = _object({"statement_id": _ref("stableId"), "relation": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 64}, "missing_ref": {"type": "string", "minLength": 1, "maxLength": 256}}, ["statement_id", "relation", "missing_ref"])
    schemas["provenance_closure_report.schema.json"] = _artifact(slug="provenance-closure-report", title="KG-MNP Provenance Closure Report 1.0", kind="KG_MNP_PROVENANCE_CLOSURE_REPORT", id_field="report_id", properties={"required_statement_count": {"type": "integer", "minimum": 0}, "closed_statement_count": {"type": "integer", "minimum": 0}, "coverage_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000}, "missing_links": _array(missing_link, maximum=100000), "orphan_records": id_list, "status": {"enum": ["PASSED", "FAILED"]}}, required=["required_statement_count", "closed_statement_count", "coverage_basis_points", "missing_links", "orphan_records", "status"])
    artifact_record = _object({"path": _ref("safePath"), "role": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 128}, "byte_sha256": _ref("sha256"), "semantic_sha256": _ref("sha256"), "size_bytes": {"type": "integer", "minimum": 0, "maximum": 1073741824}}, ["path", "role", "byte_sha256", "semantic_sha256", "size_bytes"])
    semantic_summary_fields = ["baseline_triple_count", "new_tbox_triple_count", "effective_tbox_triple_count", "abox_triple_count", "compiled_shape_triple_count", "effective_shape_triple_count", "provenance_triple_count", "review_audit_triple_count", "evidence_lineage_triple_count", "dataset_quad_count", "mapping_rule_count"]
    semantic_summary = _object({**{name: {"type": "integer", "minimum": 0} for name in semantic_summary_fields}, "semantic_dataset_digest": _ref("sha256"), "identity_payload_digest": _ref("sha256")}, [*semantic_summary_fields, "semantic_dataset_digest", "identity_payload_digest"])
    schemas["ontology_package_manifest.schema.json"] = _artifact(slug="ontology-package-manifest", title="KG-MNP Ontology Package Manifest 1.0", kind="KG_MNP_ONTOLOGY_PACKAGE", id_field="package_id", properties={"package_format_version": {"const": "1.0.0"}, "package_name": {"type": "string", "pattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$", "maxLength": 128}, "package_version": {"type": "string", "pattern": r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$", "maxLength": 64}, "package_status": {"const": "VALIDATED_UNPUBLISHED"}, "ontology_identity": _ref("ontologyIdentity"), "source_confirmed_package": _ref("stableId"), "compiler_snapshot": _ref("stableId"), "compiler_policy": _ref("stableId"), "project_lock_id": _ref("stableId"), "contract_catalog_digest": _ref("sha256"), "domain_pack_locks": id_list, "baseline_dependencies": _array(baseline_asset, maximum=10000), "graphs": _array(graph_record, maximum=32), "mapping_plan": _ref("stableId"), "validation_reports": _array(validation_ref, maximum=32, minimum=1), "provenance": _array(validation_ref, maximum=16, minimum=1), "artifacts": _array(artifact_record, maximum=10000, minimum=1), "semantic_summary": semantic_summary}, required=["package_format_version", "package_name", "package_version", "package_status", "ontology_identity", "source_confirmed_package", "compiler_snapshot", "compiler_policy", "project_lock_id", "contract_catalog_digest", "domain_pack_locks", "baseline_dependencies", "graphs", "mapping_plan", "validation_reports", "provenance", "artifacts", "semantic_summary"])
    schemas["ontology_package_lock.schema.json"] = _artifact(slug="ontology-package-lock", title="KG-MNP Ontology Package Lock 1.0", kind="KG_MNP_ONTOLOGY_PACKAGE_LOCK", id_field="lock_id", properties={"package_id": _ref("stableId"), "package_name": {"type": "string", "pattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$", "maxLength": 128}, "package_version": {"type": "string", "pattern": r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$", "maxLength": 64}, "manifest_file_sha256": _ref("sha256"), "manifest_semantic_sha256": _ref("sha256"), "payload_files": _array(_ref("fileRecord"), maximum=10000, minimum=1), "canonicalization_profile": {"const": "KG-MNP RDF Canonical Profile v1"}}, required=["package_id", "package_name", "package_version", "manifest_file_sha256", "manifest_semantic_sha256", "payload_files", "canonicalization_profile"])
    schemas["ontology_package_validation_report.schema.json"] = _artifact(slug="ontology-package-validation-report", title="KG-MNP Ontology Package Validation Report 1.0", kind="KG_MNP_ONTOLOGY_PACKAGE_VALIDATION_REPORT", id_field="report_id", properties={"package_id": _ref("stableId"), "checks": _array(_object({"check": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]*$", "maxLength": 128}, "status": {"enum": ["PASSED", "FAILED", "NOT_RUN"]}, "report_ref": {"oneOf": [_ref("stableId"), {"type": "null"}]}}, ["check", "status", "report_ref"]), maximum=64, minimum=1), "status": {"enum": ["VALID", "INVALID"]}, "issues": issue_list}, required=["package_id", "checks", "status", "issues"])
    schemas["build_reproduction_report.schema.json"] = _artifact(slug="build-reproduction-report", title="KG-MNP Build Reproduction Report 1.0", kind="KG_MNP_BUILD_REPRODUCTION_REPORT", id_field="report_id", properties={"build_id": _ref("stableId"), "package_id": _ref("stableId"), "compared_files": path_list, "matching_files": path_list, "mismatches": path_list, "archive_sha256_first": _ref("sha256"), "archive_sha256_second": _ref("sha256"), "status": {"enum": ["PASSED", "FAILED"]}}, required=["build_id", "package_id", "compared_files", "matching_files", "mismatches", "archive_sha256_first", "archive_sha256_second", "status"])
    return schemas


def _catalog_schema() -> dict[str, Any]:
    common = "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/toolchain/toolchain-common/1.0#/$defs/"
    return {
        "$schema": DRAFT,
        "$id": "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/toolchain/contract-catalog/1.2",
        "title": "KG-MNP Public Contract Catalog 1.2",
        "description": "Compatible additive catalog revision adding the compilation scope.",
        **_object(
            {
                "manifest_kind": {"const": "KG_MNP_CONTRACT_CATALOG"},
                "schema_version": {"const": "1.2.0"},
                "canonicalization_profile": {"const": "KG-MNP Canonical JSON v1"},
                "contracts": _array(
                    _object(
                        {
                            "name": {"$ref": common + "contractName"},
                            "version": {"$ref": common + "semanticVersion"},
                            "schema_id": {"$ref": common + "iri"},
                            "resource_path": {"$ref": common + "safeRelativePosixPath"},
                            "scope": {"enum": ["toolchain", "modeling", "ingestion", "compilation"]},
                            "stability": {"enum": ["stable", "retained", "experimental"]},
                            "authority_level": {"enum": ["descriptive", "proposal", "confirmed-input", "control", "lock"]},
                            "sha256": {"$ref": common + "sha256"},
                        },
                        ["name", "version", "schema_id", "resource_path", "scope", "stability", "authority_level", "sha256"],
                    ),
                    minimum=1,
                ),
            },
            ["manifest_kind", "schema_version", "canonicalization_profile", "contracts"],
        ),
    }


AUTHORITIES = {
    "compilation-common": "descriptive",
    "semantic-compiler-policy": "control",
    "semantic-compiler-snapshot": "lock",
    "compiler-input-attestation": "lock",
    "semantic-compilation-plan": "control",
    "semantic-compilation-run": "control",
    "tbox-compilation-report": "descriptive",
    "abox-compilation-report": "descriptive",
    "shacl-compilation-report": "descriptive",
    "mapping-plan": "control",
    "statement-provenance-manifest": "descriptive",
    "rdf-dataset-manifest": "control",
    "rdf-syntax-validation-report": "descriptive",
    "owl-profile-report": "descriptive",
    "semantic-owl-consistency-report": "descriptive",
    "semantic-shacl-validation-report": "descriptive",
    "competency-question-test-plan": "control",
    "competency-question-test-report": "descriptive",
    "provenance-closure-report": "descriptive",
    "ontology-package-manifest": "control",
    "ontology-package-lock": "lock",
    "ontology-package-validation-report": "descriptive",
    "build-reproduction-report": "descriptive",
}


def _expected_catalog(current: dict[str, Any], outputs: dict[Path, bytes]) -> dict[str, Any]:
    retained = [
        item for item in current["contracts"]
        if item["name"] not in {*AUTHORITIES, "contract-catalog-v1-2"}
    ]
    additions = []
    for filename, schema in sorted(_schemas().items()):
        name = filename.removesuffix(".schema.json").replace("_", "-")
        data = outputs[COMPILATION / filename]
        additions.append({
            "authority_level": AUTHORITIES[name],
            "name": name,
            "resource_path": f"schemas/compilation/{filename}",
            "schema_id": schema["$id"],
            "scope": "compilation",
            "sha256": hashlib.sha256(data).hexdigest(),
            "stability": "experimental",
            "version": "1.0.0",
        })
    catalog_data = outputs[TOOLCHAIN / "contract_catalog_v1_2.schema.json"]
    additions.append({
        "authority_level": "control",
        "name": "contract-catalog-v1-2",
        "resource_path": "schemas/toolchain/contract_catalog_v1_2.schema.json",
        "schema_id": _catalog_schema()["$id"],
        "scope": "toolchain",
        "sha256": hashlib.sha256(catalog_data).hexdigest(),
        "stability": "experimental",
        "version": "1.2.0",
    })
    return {
        **current,
        "schema_version": "1.2.0",
        "contracts": sorted(
            [*retained, *additions],
            key=lambda item: (item["scope"], item["name"], item["version"]),
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = {COMPILATION / name: _json_bytes(schema) for name, schema in _schemas().items()}
    outputs[TOOLCHAIN / "contract_catalog_v1_2.schema.json"] = _json_bytes(_catalog_schema())
    catalog_path = ROOT / "src/kg_mnp/contracts/catalog.json"
    current_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    expected_catalog = _expected_catalog(current_catalog, outputs)
    expected_catalog_bytes = _json_bytes(expected_catalog)
    stale = [path for path, data in outputs.items() if not path.is_file() or path.read_bytes() != data]
    if catalog_path.read_bytes() != expected_catalog_bytes:
        stale.append(catalog_path)
    if args.check:
        if stale:
            raise SystemExit("Prompt 5 generated schemas are stale: " + ", ".join(path.name for path in stale))
        print("Prompt 5 generated schemas are current.")
        return 0
    COMPILATION.mkdir(parents=True, exist_ok=True)
    for path, data in sorted(outputs.items()):
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)
    if catalog_path.read_bytes() != expected_catalog_bytes:
        catalog_path.write_bytes(expected_catalog_bytes)
    print(f"Generated {len(outputs)} Prompt 5 schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
