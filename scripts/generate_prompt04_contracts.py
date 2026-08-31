#!/usr/bin/env python3
"""Generate the closed Prompt 4 contract family and Catalog entries."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from kg_mnp.contracts.canonical import bytes_sha256
from kg_mnp.contracts.document_io import deterministic_json_bytes

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "src" / "kg_mnp" / "contracts" / "schemas"
MODELING_ROOT = SCHEMA_ROOT / "modeling"
TOOLCHAIN_ROOT = SCHEMA_ROOT / "toolchain"
CATALOG_PATH = ROOT / "src" / "kg_mnp" / "contracts" / "catalog.json"
BASE = "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling"
TOOLCHAIN_BASE = "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/toolchain"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
HEX = "^[0-9a-f]{64}$"
URN = "^urn:kg-mnp:[a-z0-9-]+:[0-9a-f]{64}$"
# Contract syntax permits references to the canonical HTTP RDF/RDFS/OWL/XSD/
# SHACL namespaces. Runtime namespace policy still forbids minting new HTTP IRIs.
IRI = "^(?:https?://|urn:)[^\\s]+$"


def string(*, max_length: int = 4096, min_length: int = 1, pattern: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"type": "string", "minLength": min_length, "maxLength": max_length}
    if pattern is not None:
        value["pattern"] = pattern
    return value


def id_string() -> dict[str, Any]:
    return string(max_length=256, pattern=URN)


def digest() -> dict[str, Any]:
    return string(max_length=64, pattern=HEX)


def iri() -> dict[str, Any]:
    return string(max_length=2048, pattern=IRI)


def array(items: dict[str, Any], *, max_items: int = 100000, min_items: int = 0, unique: bool = True) -> dict[str, Any]:
    return {
        "type": "array",
        "items": items,
        "minItems": min_items,
        "maxItems": max_items,
        "uniqueItems": unique,
    }


def closed(properties: dict[str, Any], required: list[str] | tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(required),
        "properties": properties,
    }


def issue_schema() -> dict[str, Any]:
    return closed(
        {
            "issue_id": id_string(),
            "code": string(max_length=128, pattern="^[A-Z][A-Z0-9_]*$"),
            "severity": {"enum": ["INFO", "WARNING", "BLOCKING"]},
            "message": string(max_length=4096),
            "candidate_refs": array(id_string(), max_items=10000),
            "evidence_refs": array(id_string(), max_items=10000),
        },
        ["issue_id", "code", "severity", "message", "candidate_refs", "evidence_refs"],
    )


def manifest_schema(name: str, kind: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    slug = name.replace("_", "-")
    common = {
        "manifest_kind": {"const": kind},
        "schema_version": {"const": "1.0.0"},
    }
    return {
        "$schema": DRAFT,
        "$id": f"{BASE}/{slug.removeprefix('ontology-')}/1.0" if False else f"{BASE}/{slug}/1.0",
        "title": f"KG-MNP {name.replace('_', ' ').title()} 1.0",
        **closed({**common, **properties}, ["manifest_kind", "schema_version", *required]),
    }


def candidate_body() -> dict[str, Any]:
    types = [
        "CLASS", "OBJECT_PROPERTY", "DATA_PROPERTY", "SUBCLASS_AXIOM", "DOMAIN_AXIOM",
        "RANGE_AXIOM", "DISJOINT_CLASSES_AXIOM", "RECORD_TO_CLASS",
        "FIELD_TO_DATA_PROPERTY", "REFERENCE_TO_OBJECT_PROPERTY", "VALUE_MAPPING",
        "IRI_TEMPLATE", "NULL_HANDLING_POLICY", "INDIVIDUAL", "CLASS_ASSERTION",
        "DATA_PROPERTY_ASSERTION", "OBJECT_PROPERTY_ASSERTION", "NODE_SHAPE",
        "PROPERTY_SHAPE", "MIN_COUNT", "MAX_COUNT", "DATATYPE", "CLASS_CONSTRAINT",
        "NODE_KIND", "IN_VALUES",
    ]
    return closed(
        {
            "candidate_type": {"enum": types},
            "subject_iri": {"oneOf": [iri(), {"type": "null"}]},
            "predicate_iri": {"oneOf": [iri(), {"type": "null"}]},
            "object_iri": {"oneOf": [iri(), {"type": "null"}]},
            "label": {"oneOf": [string(max_length=512), {"type": "null"}]},
            "source_field": {"oneOf": [string(max_length=512), {"type": "null"}]},
            "target_iri": {"oneOf": [iri(), {"type": "null"}]},
            "literal": {
                "oneOf": [
                    closed(
                        {
                            "lexical_value": string(max_length=16384, min_length=0),
                            "datatype_iri": {"oneOf": [iri(), {"type": "null"}]},
                            "language": {"oneOf": [string(max_length=35, pattern="^[A-Za-z0-9-]+$"), {"type": "null"}]},
                        },
                        ["lexical_value", "datatype_iri", "language"],
                    ),
                    {"type": "null"},
                ]
            },
            "values": array(string(max_length=4096, min_length=0), max_items=1024),
            "integer_value": {"oneOf": [{"type": "integer", "minimum": 0, "maximum": 1000000}, {"type": "null"}]},
            "conversion_policy": {"enum": ["IDENTITY", "TRIM", "NFC", "LOWERCASE", "UPPERCASE", "CONTROLLED_LOOKUP", "NONE"]},
            "null_policy": {"enum": ["REJECT", "OMIT", "PRESERVE", "CONTROLLED_DEFAULT", "NONE"]},
        },
        [
            "candidate_type", "subject_iri", "predicate_iri", "object_iri", "label",
            "source_field", "target_iri", "literal", "values", "integer_value",
            "conversion_policy", "null_policy",
        ],
    )


def candidate() -> dict[str, Any]:
    return closed(
        {
            "candidate_id": id_string(),
            "candidate_kind": {"enum": ["TBOX", "MAPPING", "ABOX", "SHACL"]},
            "publication_scope": {"enum": ["TBOX", "MAPPING", "ABOX", "SHACL"]},
            "candidate_action": {"enum": ["REUSE_EXISTING", "CREATE_NEW", "ALIGN_TO_EXISTING", "ASSERT", "CONSTRAIN"]},
            "semantic_signature": digest(),
            "kg_ir_item_refs": array(id_string(), max_items=10000),
            "evidence_refs": array(id_string(), max_items=10000),
            "domain_asset_refs": array(string(max_length=512), max_items=10000),
            "competency_question_refs": array(id_string(), max_items=10000),
            "baseline_element_refs": array(id_string(), max_items=10000),
            "provider_snapshot_refs": array(id_string(), max_items=128),
            "model_invocation_refs": array(id_string(), max_items=128),
            "dependency_candidate_refs": array(id_string(), max_items=128),
            "rationale": string(max_length=16384),
            "provider_rationales": array(closed({"provider_snapshot_id": id_string(), "rationale": string(max_length=16384)}, ["provider_snapshot_id", "rationale"]), max_items=128),
            "support_status": {"enum": ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"]},
            "score_basis": string(max_length=1024),
            "score_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000},
            "review_required": {"const": True},
            "issues": array(issue_schema(), max_items=10000),
            "body": candidate_body(),
        },
        [
            "candidate_id", "candidate_kind", "publication_scope", "candidate_action",
            "semantic_signature", "kg_ir_item_refs", "evidence_refs", "domain_asset_refs",
            "competency_question_refs", "baseline_element_refs", "provider_snapshot_refs",
            "model_invocation_refs", "dependency_candidate_refs", "rationale",
            "provider_rationales", "support_status", "score_basis", "score_basis_points",
            "review_required", "issues", "body",
        ],
    )


def schemas() -> dict[Path, dict[str, Any]]:
    result: dict[Path, dict[str, Any]] = {}
    common = {
        "$schema": DRAFT,
        "$id": f"{BASE}/ontology-modeling-common/1.0",
        "title": "KG-MNP Ontology Modeling Common 1.0",
        "$defs": {"stableId": id_string(), "digest": digest(), "iri": iri(), "issue": issue_schema(), "candidate": candidate()},
        **closed({}, []),
    }
    result[MODELING_ROOT / "ontology_modeling_common.schema.json"] = common

    namespace_policy = closed(
        {
            "default_namespace": iri(),
            "allowed_new_namespaces": array(iri(), max_items=128),
            "reusable_namespaces": array(iri(), max_items=128),
            # RDF/RDFS/OWL/XSD/SHACL canonical namespaces are historically HTTP;
            # they are recorded only as read-only prefixes, never minting targets.
            "reserved_namespaces": array(string(max_length=2048), max_items=128),
            "allowed_iri_schemes": {"type": "array", "items": {"enum": ["https", "urn"]}, "minItems": 1, "maxItems": 2, "uniqueItems": True},
            "external_iri_policy": {"enum": ["DENY", "REUSE_ONLY", "ALLOW_LISTED"]},
        },
        ["default_namespace", "allowed_new_namespaces", "reusable_namespaces", "reserved_namespaces", "allowed_iri_schemes", "external_iri_policy"],
    )
    scope = manifest_schema(
        "ontology-scope", "KG_MNP_ONTOLOGY_SCOPE",
        {
            "scope_id": id_string(), "project_id": string(max_length=256), "project_lock_id": id_string(),
            "domain_pack_locks": array(id_string(), max_items=32, min_items=1),
            "kg_ir_dataset_ids": array(id_string(), max_items=128, min_items=1),
            "modeling_intent": {"enum": ["CREATE_NEW_ONTOLOGY", "EXTEND_BASELINE", "ALIGN_TO_BASELINE", "INSTANCE_POPULATION", "MAPPING_ONLY", "MIXED_MODELING"]},
            "domain_description": string(max_length=16384),
            "target_object_families": array(string(max_length=512), max_items=1024),
            "in_scope": array(string(max_length=2048), max_items=4096), "out_of_scope": array(string(max_length=2048), max_items=4096),
            "target_artifacts": {"type": "array", "items": {"enum": ["TBOX", "ABOX", "MAPPING", "SHACL", "TERMINOLOGY"]}, "minItems": 1, "maxItems": 5, "uniqueItems": True},
            "namespace_policy": namespace_policy,
            "language_policy": closed({"default_language": string(max_length=35), "allowed_languages": array(string(max_length=35), max_items=64, min_items=1)}, ["default_language", "allowed_languages"]),
            "iri_minting_policy": closed({"strategy": {"enum": ["HUMAN_READABLE_SLUG", "CONTENT_HASH"]}, "slug_pattern": string(max_length=256), "allow_random_uuid": {"const": False}}, ["strategy", "slug_pattern", "allow_random_uuid"]),
            "baseline_policy": {"enum": ["REUSE_FIRST", "REUSE_REQUIRED", "NEW_ALLOWED"]},
            "competency_question_set_id": {"oneOf": [id_string(), {"type": "null"}]},
            "acceptance_gates": array(string(max_length=256), max_items=128),
            "prohibited_operations": array(string(max_length=256), max_items=128, min_items=1),
            "content_digest": digest(),
        },
        ["scope_id", "project_id", "project_lock_id", "domain_pack_locks", "kg_ir_dataset_ids", "modeling_intent", "domain_description", "target_object_families", "in_scope", "out_of_scope", "target_artifacts", "namespace_policy", "language_policy", "iri_minting_policy", "baseline_policy", "competency_question_set_id", "acceptance_gates", "prohibited_operations", "content_digest"],
    )
    result[MODELING_ROOT / "ontology_scope.schema.json"] = scope

    approval = manifest_schema(
        "ontology-scope-approval", "KG_MNP_ONTOLOGY_SCOPE_APPROVAL",
        {
            "approval_id": id_string(), "scope_id": id_string(), "scope_semantic_hash": digest(),
            "reviewer_id": string(max_length=256), "reviewer_role": string(max_length=128),
            "decision": {"enum": ["APPROVE", "REJECT", "REQUEST_CHANGES"]}, "rationale": string(max_length=16384),
            "operational_metadata": closed({"decided_at": {"oneOf": [string(max_length=64), {"type": "null"}]}, "display_name": {"oneOf": [string(max_length=256), {"type": "null"}]}}, ["decided_at", "display_name"]),
            "decision_semantic_hash": digest(),
        },
        ["approval_id", "scope_id", "scope_semantic_hash", "reviewer_id", "reviewer_role", "decision", "rationale", "operational_metadata", "decision_semantic_hash"],
    )
    result[MODELING_ROOT / "ontology_scope_approval.schema.json"] = approval

    question = closed(
        {
            "question_id": id_string(), "question_text": string(max_length=8192), "purpose": string(max_length=4096),
            "priority": {"enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
            "expected_answer_shape": {"enum": ["BOOLEAN", "ENTITY_LIST", "SCALAR", "TABLE", "GRAPH_PATTERN"]},
            "required_concepts": array(string(max_length=2048), max_items=256),
            "required_relations": array(string(max_length=2048), max_items=256),
            "required_constraints": array(string(max_length=2048), max_items=256),
            "evidence_refs": array(id_string(), max_items=10000), "source_domain_asset_refs": array(string(max_length=512), max_items=1024),
            "validation_intent": {"enum": ["RETRIEVAL", "CONSTRAINT_CHECK", "INFERENCE", "TRACEABILITY"]},
            "status": {"enum": ["DRAFT", "APPROVED", "RETIRED"]},
        },
        ["question_id", "question_text", "purpose", "priority", "expected_answer_shape", "required_concepts", "required_relations", "required_constraints", "evidence_refs", "source_domain_asset_refs", "validation_intent", "status"],
    )
    cq = manifest_schema("competency-question-set", "KG_MNP_COMPETENCY_QUESTION_SET", {"question_set_id": id_string(), "project_lock_id": id_string(), "scope_id": id_string(), "questions": array(question, max_items=10000, min_items=1), "content_digest": digest()}, ["question_set_id", "project_lock_id", "scope_id", "questions", "content_digest"])
    result[MODELING_ROOT / "competency_question_set.schema.json"] = cq

    coverage_item = closed({"question_id": id_string(), "status": {"enum": ["COVERED", "PARTIAL", "GAP"]}, "candidate_refs": array(id_string(), max_items=10000), "issue_refs": array(id_string(), max_items=10000), "structural_only": {"const": True}}, ["question_id", "status", "candidate_refs", "issue_refs", "structural_only"])
    coverage = manifest_schema("competency-question-coverage-report", "KG_MNP_COMPETENCY_QUESTION_COVERAGE_REPORT", {"coverage_report_id": id_string(), "question_set_id": id_string(), "proposal_id": id_string(), "coverage": array(coverage_item, max_items=10000), "execution_claimed": {"const": False}, "content_digest": digest()}, ["coverage_report_id", "question_set_id", "proposal_id", "coverage", "execution_claimed", "content_digest"])
    result[MODELING_ROOT / "competency_question_coverage_report.schema.json"] = coverage

    element = closed({"element_id": id_string(), "element_kind": {"enum": ["CLASS", "OBJECT_PROPERTY", "DATA_PROPERTY", "ANNOTATION_PROPERTY", "INDIVIDUAL", "SHAPE", "AXIOM"]}, "iri": iri(), "source_asset_id": string(max_length=512), "source_sha256": digest(), "labels": array(closed({"value": string(max_length=1024), "language": {"oneOf": [string(max_length=35), {"type": "null"}]}}, ["value", "language"]), max_items=128), "definition": {"oneOf": [string(max_length=16384), {"type": "null"}]}, "domain_refs": array(iri(), max_items=128), "range_refs": array(iri(), max_items=128), "parent_refs": array(iri(), max_items=128)}, ["element_id", "element_kind", "iri", "source_asset_id", "source_sha256", "labels", "definition", "domain_refs", "range_refs", "parent_refs"])
    index = closed({"iri_index": array(closed({"key": string(max_length=2048), "element_ids": array(id_string(), max_items=10000, min_items=1)}, ["key", "element_ids"]), max_items=100000), "label_index": array(closed({"key": string(max_length=1024), "element_ids": array(id_string(), max_items=10000, min_items=1)}, ["key", "element_ids"]), max_items=100000), "normalized_label_index": array(closed({"key": string(max_length=1024), "element_ids": array(id_string(), max_items=10000, min_items=1)}, ["key", "element_ids"]), max_items=100000), "language_index": array(closed({"key": string(max_length=35), "element_ids": array(id_string(), max_items=10000)}, ["key", "element_ids"]), max_items=1000), "property_type_index": array(closed({"key": string(max_length=64), "element_ids": array(id_string(), max_items=10000)}, ["key", "element_ids"]), max_items=64), "domain_range_index": array(closed({"key": string(max_length=2048), "element_ids": array(id_string(), max_items=10000)}, ["key", "element_ids"]), max_items=100000), "hierarchy_index": array(closed({"key": string(max_length=2048), "element_ids": array(id_string(), max_items=10000)}, ["key", "element_ids"]), max_items=100000), "source_asset_index": array(closed({"key": string(max_length=512), "element_ids": array(id_string(), max_items=10000)}, ["key", "element_ids"]), max_items=100000)}, ["iri_index", "label_index", "normalized_label_index", "language_index", "property_type_index", "domain_range_index", "hierarchy_index", "source_asset_index"])
    baseline_props = {"baseline_snapshot_id": id_string(), "project_lock_id": id_string(), "domain_pack_lock_ids": array(id_string(), max_items=32, min_items=1), "ontology_assets": array(closed({"asset_id": string(max_length=512), "relative_path": string(max_length=1024, pattern="^(?![A-Za-z]:|/|\\\\|.*(?:^|/)\\.\\.(?:/|$)).+$"), "sha256": digest()}, ["asset_id", "relative_path", "sha256"]), max_items=10000), "ontology_iris": array(iri(), max_items=10000), "version_iris": array(iri(), max_items=10000), "imports": array(closed({"source_iri": iri(), "import_iri": iri(), "local_asset_id": string(max_length=512), "remote_fetch": {"const": False}}, ["source_iri", "import_iri", "local_asset_id", "remote_fetch"]), max_items=10000), "elements": array(element, max_items=1000000), "classes": array(id_string(), max_items=1000000), "object_properties": array(id_string(), max_items=1000000), "data_properties": array(id_string(), max_items=1000000), "annotation_properties": array(id_string(), max_items=1000000), "individuals": array(id_string(), max_items=1000000), "shapes": array(id_string(), max_items=1000000), "labels": array(id_string(), max_items=1000000), "definitions": array(id_string(), max_items=1000000), "domain_axioms": array(id_string(), max_items=1000000), "range_axioms": array(id_string(), max_items=1000000), "subclass_axioms": array(id_string(), max_items=1000000), "indexes": index, "content_digest": digest()}
    baseline = manifest_schema("ontology-baseline-snapshot", "KG_MNP_ONTOLOGY_BASELINE_SNAPSHOT", baseline_props, list(baseline_props))
    result[MODELING_ROOT / "ontology_baseline_snapshot.schema.json"] = baseline

    term = closed({"term_id": id_string(), "lexical_form": string(max_length=2048), "normalized_form": string(max_length=2048), "language": {"oneOf": [string(max_length=35), {"type": "null"}]}, "source_type": {"enum": ["DOMAIN_PACK", "ONTOLOGY_BASELINE", "APPROVED_SCOPE", "KG_IR", "HUMAN_AUTHORED"]}, "source_ref": string(max_length=512), "evidence_refs": array(id_string(), max_items=10000), "candidate_iris": array(iri(), max_items=128), "definition": {"oneOf": [string(max_length=16384), {"type": "null"}]}, "aliases": array(string(max_length=2048), max_items=128), "status": {"enum": ["PROPOSED", "REVIEW_REQUIRED", "HUMAN_AUTHORED"]}}, ["term_id", "lexical_form", "normalized_form", "language", "source_type", "source_ref", "evidence_refs", "candidate_iris", "definition", "aliases", "status"])
    terminology = manifest_schema("terminology-catalog", "KG_MNP_TERMINOLOGY_CATALOG", {"terminology_catalog_id": id_string(), "project_lock_id": id_string(), "scope_id": id_string(), "baseline_snapshot_id": id_string(), "kg_ir_dataset_ids": array(id_string(), max_items=128), "terms": array(term, max_items=100000), "content_digest": digest()}, ["terminology_catalog_id", "project_lock_id", "scope_id", "baseline_snapshot_id", "kg_ir_dataset_ids", "terms", "content_digest"])
    result[MODELING_ROOT / "terminology_catalog.schema.json"] = terminology

    alignment = closed({"alignment_id": id_string(), "source_term_id": id_string(), "target_element_id": {"oneOf": [id_string(), {"type": "null"}]}, "target_iri": {"oneOf": [iri(), {"type": "null"}]}, "alignment_type": {"enum": ["EXACT_IRI", "EXACT_LABEL", "NORMALIZED_LABEL", "DECLARED_ALIAS", "DECLARED_SYNONYM", "LEXICAL_SIMILARITY", "NO_MATCH"]}, "score_basis": string(max_length=1024), "score_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000}, "provider_snapshot_id": {"oneOf": [id_string(), {"type": "null"}]}, "evidence_refs": array(id_string(), max_items=10000), "rationale": string(max_length=16384), "ambiguity_group": {"oneOf": [id_string(), {"type": "null"}]}, "review_required": {"const": True}}, ["alignment_id", "source_term_id", "target_element_id", "target_iri", "alignment_type", "score_basis", "score_basis_points", "provider_snapshot_id", "evidence_refs", "rationale", "ambiguity_group", "review_required"])
    alignments = manifest_schema("term-alignment-set", "KG_MNP_TERM_ALIGNMENT_SET", {"term_alignment_set_id": id_string(), "terminology_catalog_id": id_string(), "baseline_snapshot_id": id_string(), "alignments": array(alignment, max_items=1000000), "content_digest": digest()}, ["term_alignment_set_id", "terminology_catalog_id", "baseline_snapshot_id", "alignments", "content_digest"])
    result[MODELING_ROOT / "term_alignment_set.schema.json"] = alignments

    field_mapping = closed({"field_mapping_id": id_string(), "source_item_id": id_string(), "source_field_name": string(max_length=512), "source_item_kind": string(max_length=128), "source_datatype": string(max_length=256), "target_class_iri": {"oneOf": [iri(), {"type": "null"}]}, "target_property_iri": {"oneOf": [iri(), {"type": "null"}]}, "mapping_kind": {"enum": ["RECORD_TO_CLASS", "FIELD_TO_DATA_PROPERTY", "REFERENCE_TO_OBJECT_PROPERTY", "VALUE_MAPPING", "IRI_TEMPLATE", "NULL_HANDLING_POLICY"]}, "conversion_policy": {"enum": ["IDENTITY", "TRIM", "NFC", "LOWERCASE", "UPPERCASE", "CONTROLLED_LOOKUP", "NONE"]}, "null_policy": {"enum": ["REJECT", "OMIT", "PRESERVE", "CONTROLLED_DEFAULT", "NONE"]}, "cardinality_observation": string(max_length=256), "evidence_refs": array(id_string(), max_items=10000), "rationale": string(max_length=16384), "provider_refs": array(id_string(), max_items=128), "review_required": {"const": True}}, ["field_mapping_id", "source_item_id", "source_field_name", "source_item_kind", "source_datatype", "target_class_iri", "target_property_iri", "mapping_kind", "conversion_policy", "null_policy", "cardinality_observation", "evidence_refs", "rationale", "provider_refs", "review_required"])
    field_set = manifest_schema("field-mapping-candidate-set", "KG_MNP_FIELD_MAPPING_CANDIDATE_SET", {"field_mapping_candidate_set_id": id_string(), "kg_ir_dataset_ids": array(id_string(), max_items=128, min_items=1), "mappings": array(field_mapping, max_items=100000), "content_digest": digest()}, ["field_mapping_candidate_set_id", "kg_ir_dataset_ids", "mappings", "content_digest"])
    result[MODELING_ROOT / "field_mapping_candidate_set.schema.json"] = field_set

    input_props = {"modeling_input_bundle_id": id_string(), "project_lock_id": id_string(), "contract_catalog_digest": digest(), "domain_pack_lock_ids": array(id_string(), max_items=32, min_items=1), "approved_scope_id": id_string(), "scope_approval_id": id_string(), "competency_question_set_id": id_string(), "baseline_snapshot_id": id_string(), "terminology_catalog_id": id_string(), "term_alignment_set_id": id_string(), "kg_ir_dataset_ids": array(id_string(), max_items=128, min_items=1), "evidence_record_ids": array(id_string(), max_items=100000, min_items=1), "provider_policy": closed({"allowed_provider_ids": array(string(max_length=128), max_items=128), "network_allowed": {"const": False}, "authority_level": {"const": "PROPOSAL_ONLY"}}, ["allowed_provider_ids", "network_allowed", "authority_level"]), "review_policy_id": id_string(), "review_required_dataset_acceptances": array(id_string(), max_items=128), "content_digest": digest()}
    input_bundle = manifest_schema("modeling-input-bundle", "KG_MNP_MODELING_INPUT_BUNDLE", input_props, list(input_props))
    result[MODELING_ROOT / "modeling_input_bundle.schema.json"] = input_bundle

    request_props = {"request_id": id_string(), "modeling_input_bundle_id": id_string(), "provider_snapshot_id": id_string(), "capability": {"enum": ["terminology-alignment", "baseline-reuse", "tbox-proposal", "field-mapping-proposal", "abox-proposal", "shacl-proposal", "repair-suggestion"]}, "immutable_payload": closed({"scope_id": id_string(), "baseline_snapshot_id": id_string(), "terminology_catalog_id": id_string(), "term_alignment_set_id": id_string(), "kg_ir_dataset_ids": array(id_string(), max_items=128), "evidence_record_ids": array(id_string(), max_items=100000)}, ["scope_id", "baseline_snapshot_id", "terminology_catalog_id", "term_alignment_set_id", "kg_ir_dataset_ids", "evidence_record_ids"]), "limits": closed({name: {"type": "integer", "minimum": 1, "maximum": 1000000000} for name in ["max_total_candidates", "max_candidate_dependencies", "max_model_response_bytes", "max_model_json_depth", "max_rationale_characters"]}, ["max_total_candidates", "max_candidate_dependencies", "max_model_response_bytes", "max_model_json_depth", "max_rationale_characters"]), "request_digest": digest()}
    provider_request = manifest_schema("modeling-provider-request", "KG_MNP_MODELING_PROVIDER_REQUEST", request_props, list(request_props))
    result[MODELING_ROOT / "modeling_provider_request.schema.json"] = provider_request

    draft = closed({"draft_kind": {"enum": ["TBOX", "MAPPING", "ABOX", "SHACL"]}, "candidate_action": {"enum": ["REUSE_EXISTING", "CREATE_NEW", "ALIGN_TO_EXISTING", "ASSERT", "CONSTRAIN"]}, "body": candidate_body(), "kg_ir_item_refs": array(id_string(), max_items=10000), "evidence_refs": array(id_string(), max_items=10000), "domain_asset_refs": array(string(max_length=512), max_items=10000), "competency_question_refs": array(id_string(), max_items=10000), "baseline_element_refs": array(id_string(), max_items=10000), "dependency_draft_refs": array(string(max_length=128), max_items=128), "draft_ref": string(max_length=128), "rationale": string(max_length=16384), "support_status": {"enum": ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"]}, "score_basis": string(max_length=1024), "score_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000}}, ["draft_kind", "candidate_action", "body", "kg_ir_item_refs", "evidence_refs", "domain_asset_refs", "competency_question_refs", "baseline_element_refs", "dependency_draft_refs", "draft_ref", "rationale", "support_status", "score_basis", "score_basis_points"])
    response_props = {"response_id": id_string(), "request_id": id_string(), "provider_snapshot_id": id_string(), "authority_level": {"const": "PROPOSAL_ONLY"}, "candidate_drafts": array(draft, max_items=100000), "issues": array(issue_schema(), max_items=10000), "response_digest": digest()}
    provider_response = manifest_schema("modeling-provider-response", "KG_MNP_MODELING_PROVIDER_RESPONSE", response_props, list(response_props))
    result[MODELING_ROOT / "modeling_provider_response.schema.json"] = provider_response

    invocation_props = {"invocation_id": id_string(), "provider_type": {"const": "RECORDED_EXTERNAL_MODEL"}, "provider_name": string(max_length=256), "model_id": string(max_length=512), "model_revision": string(max_length=512), "request_artifact_ref": string(max_length=1024), "request_sha256": digest(), "response_artifact_ref": string(max_length=1024), "response_sha256": digest(), "prompt_template_id": string(max_length=512), "prompt_template_sha256": digest(), "sampling_parameters": closed({"temperature_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000}, "top_p_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000}, "max_output_tokens": {"type": "integer", "minimum": 1, "maximum": 1000000}}, []), "declared_seed": {"oneOf": [{"type": "integer", "minimum": 0}, {"type": "null"}]}, "determinism_class": {"enum": ["RECORDED_BYTES_ONLY", "SEEDED_BUT_NOT_GUARANTEED", "NONDETERMINISTIC"]}, "finish_status": string(max_length=128), "parse_status": {"enum": ["VALID", "REJECTED", "PARTIAL"]}, "issues": array(issue_schema(), max_items=10000), "semantic_digest": digest()}
    invocation = manifest_schema("model-invocation-record", "KG_MNP_MODEL_INVOCATION_RECORD", invocation_props, list(invocation_props))
    result[MODELING_ROOT / "model_invocation_record.schema.json"] = invocation

    candidate_set = manifest_schema("ontology-candidate-set", "KG_MNP_ONTOLOGY_CANDIDATE_SET", {"candidate_set_id": id_string(), "request_ids": array(id_string(), max_items=128), "candidates": array(candidate(), max_items=100000), "conflicts": array(issue_schema(), max_items=100000), "content_digest": digest()}, ["candidate_set_id", "request_ids", "candidates", "conflicts", "content_digest"])
    result[MODELING_ROOT / "ontology_candidate_set.schema.json"] = candidate_set

    proposal_props = {"proposal_id": id_string(), "project_lock_id": id_string(), "modeling_input_bundle_id": id_string(), "scope_id": id_string(), "competency_question_set_id": id_string(), "baseline_snapshot_id": id_string(), "terminology_catalog_id": id_string(), "term_alignment_set_id": id_string(), "field_mapping_candidate_set_id": id_string(), "provider_snapshots": array(id_string(), max_items=128), "model_invocation_records": array(id_string(), max_items=128), "tbox_candidates": array(candidate(), max_items=100000), "mapping_candidates": array(candidate(), max_items=100000), "abox_candidates": array(candidate(), max_items=100000), "shacl_candidates": array(candidate(), max_items=100000), "conflicts": array(issue_schema(), max_items=100000), "issues": array(issue_schema(), max_items=100000), "coverage_summary": closed({"covered": {"type": "integer", "minimum": 0}, "partial": {"type": "integer", "minimum": 0}, "gaps": {"type": "integer", "minimum": 0}, "execution_claimed": {"const": False}}, ["covered", "partial", "gaps", "execution_claimed"]), "evidence_summary": closed({"candidate_count": {"type": "integer", "minimum": 0}, "with_evidence": {"type": "integer", "minimum": 0}, "coverage_basis_points": {"type": "integer", "minimum": 0, "maximum": 10000}}, ["candidate_count", "with_evidence", "coverage_basis_points"]), "authority_level": {"const": "PROPOSAL_ONLY"}, "content_digest": digest()}
    proposal = manifest_schema("ontology-modeling-proposal", "KG_MNP_ONTOLOGY_MODELING_PROPOSAL", proposal_props, list(proposal_props))
    result[MODELING_ROOT / "ontology_modeling_proposal.schema.json"] = proposal

    check = closed({"check_id": string(max_length=128), "status": {"enum": ["PASS", "REVIEW_REQUIRED", "FAIL"]}, "issues": array(issue_schema(), max_items=10000)}, ["check_id", "status", "issues"])
    prevalidation_props = {"formal_prevalidation_report_id": id_string(), "proposal_id": id_string(), "proposal_digest": digest(), "status": {"enum": ["PASS", "REVIEW_REQUIRED", "FAIL"]}, "checks": array(check, max_items=256, min_items=1), "issues": array(issue_schema(), max_items=100000), "owl_consistency_claimed": {"const": False}, "shacl_execution_claimed": {"const": False}, "cq_execution_claimed": {"const": False}, "content_digest": digest()}
    prevalidation = manifest_schema("formal-prevalidation-report", "KG_MNP_FORMAL_PREVALIDATION_REPORT", prevalidation_props, list(prevalidation_props))
    result[MODELING_ROOT / "formal_prevalidation_report.schema.json"] = prevalidation

    policy_props = {"policy_id": id_string(), "project_lock_id": id_string(), "policy_profile": {"enum": ["DEVELOPMENT_SINGLE_REVIEWER", "PRODUCTION_MULTI_ROLE"]}, "candidate_scope_rules": array(closed({"publication_scope": {"enum": ["TBOX", "MAPPING", "ABOX", "SHACL"]}, "required_roles": array(string(max_length=128), max_items=16, min_items=1), "minimum_approvals": {"type": "integer", "minimum": 1, "maximum": 16}}, ["publication_scope", "required_roles", "minimum_approvals"]), max_items=16, min_items=1), "required_roles": array(string(max_length=128), max_items=64, min_items=1), "minimum_approvals": {"type": "integer", "minimum": 1, "maximum": 16}, "evidence_requirements": {"enum": ["ALL_ACCEPTED", "DOMAIN_EVIDENCE_ALLOWED"]}, "modification_policy": {"const": "NEW_REVISION_AND_REVALIDATE"}, "blocking_issue_policy": {"const": "MUST_RESOLVE"}, "quorum_policy": {"enum": ["PER_SCOPE", "GLOBAL"]}, "self_approval_policy": {"const": "PROVIDER_PROHIBITED"}, "development_only": {"type": "boolean"}, "content_digest": digest()}
    policy = manifest_schema("ontology-review-policy", "KG_MNP_ONTOLOGY_REVIEW_POLICY", policy_props, list(policy_props))
    result[MODELING_ROOT / "ontology_review_policy.schema.json"] = policy

    queue_item = closed({"queue_item_id": id_string(), "candidate_id": {"oneOf": [id_string(), {"type": "null"}]}, "issue_id": {"oneOf": [id_string(), {"type": "null"}]}, "item_type": {"enum": ["SCOPE", "TERMINOLOGY_ALIGNMENT", "CANDIDATE", "CONFLICT", "COVERAGE_GAP"]}, "publication_scope": {"oneOf": [{"enum": ["TBOX", "MAPPING", "ABOX", "SHACL"]}, {"type": "null"}]}, "dependency_refs": array(id_string(), max_items=128), "evidence_refs": array(id_string(), max_items=10000), "competency_question_refs": array(id_string(), max_items=10000), "prevalidation_status": {"enum": ["PASS", "REVIEW_REQUIRED", "FAIL"]}, "required_roles": array(string(max_length=128), max_items=16), "review_state": {"enum": ["BLOCKED", "READY_FOR_REVIEW", "NEEDS_EVIDENCE", "UNDER_REVIEW", "DECIDED", "SUPERSEDED"]}, "blocking_reasons": array(string(max_length=4096), max_items=10000), "priority": {"type": "integer", "minimum": 0, "maximum": 1000000}}, ["queue_item_id", "candidate_id", "issue_id", "item_type", "publication_scope", "dependency_refs", "evidence_refs", "competency_question_refs", "prevalidation_status", "required_roles", "review_state", "blocking_reasons", "priority"])
    queue_props = {"review_queue_id": id_string(), "project_lock_id": id_string(), "proposal_id": id_string(), "proposal_digest": digest(), "formal_prevalidation_report_id": id_string(), "review_policy_id": id_string(), "items": array(queue_item, max_items=100000), "content_digest": digest()}
    queue = manifest_schema("ontology-review-queue", "KG_MNP_ONTOLOGY_REVIEW_QUEUE", queue_props, list(queue_props))
    result[MODELING_ROOT / "ontology_review_queue.schema.json"] = queue

    action_props = {"action_id": id_string(), "review_queue_id": id_string(), "project_lock_id": id_string(), "sequence": {"type": "integer", "minimum": 1, "maximum": 1000000}, "previous_action_hash": {"oneOf": [digest(), {"type": "null"}]}, "candidate_id": {"oneOf": [id_string(), {"type": "null"}]}, "issue_id": {"oneOf": [id_string(), {"type": "null"}]}, "decision": {"enum": ["ACCEPT", "MODIFY_AND_ACCEPT", "REJECT", "DEFER", "REQUEST_EVIDENCE", "REUSE_EXISTING", "MARK_DUPLICATE", "RESOLVE_CONFLICT", "COMMENT"]}, "reviewer_id": string(max_length=256), "reviewer_role": string(max_length=128), "rationale": string(max_length=16384), "modified_candidate": {"oneOf": [candidate(), {"type": "null"}]}, "baseline_element_ref": {"oneOf": [id_string(), {"type": "null"}]}, "evidence_refs": array(id_string(), max_items=10000), "operational_metadata": closed({"decided_at": {"oneOf": [string(max_length=64), {"type": "null"}]}, "session_id": {"oneOf": [string(max_length=256), {"type": "null"}]}, "display_name": {"oneOf": [string(max_length=256), {"type": "null"}]}}, ["decided_at", "session_id", "display_name"]), "semantic_action_hash": digest(), "action_hash": digest()}
    action = manifest_schema("ontology-review-action", "KG_MNP_ONTOLOGY_REVIEW_ACTION", action_props, list(action_props))
    result[MODELING_ROOT / "ontology_review_action.schema.json"] = action

    decision_props = {"review_decision_log_id": id_string(), "review_queue_id": id_string(), "project_lock_id": id_string(), "proposal_id": id_string(), "proposal_digest": digest(), "prevalidation_report_id": id_string(), "prevalidation_digest": digest(), "review_policy_id": id_string(), "review_policy_digest": digest(), "action_ids": array(id_string(), max_items=100000), "final_decisions": array(closed({"candidate_id": id_string(), "decision": {"enum": ["ACCEPT", "MODIFY_AND_ACCEPT", "REJECT", "DEFER", "REUSE_EXISTING", "MARK_DUPLICATE"]}, "effective_candidate_id": {"oneOf": [id_string(), {"type": "null"}]}, "reviewer_ids": array(string(max_length=256), max_items=16), "reviewer_roles": array(string(max_length=128), max_items=16)}, ["candidate_id", "decision", "effective_candidate_id", "reviewer_ids", "reviewer_roles"]), max_items=100000), "operational_log_hash": digest(), "semantic_decision_hash": digest(), "content_digest": digest()}
    decision_log = manifest_schema("ontology-review-decision-log", "KG_MNP_ONTOLOGY_REVIEW_DECISION_LOG", decision_props, list(decision_props))
    result[MODELING_ROOT / "ontology_review_decision_log.schema.json"] = decision_log

    closure = closed({"required_count": {"type": "integer", "minimum": 0}, "closed_count": {"type": "integer", "minimum": 0}, "coverage_basis_points": {"const": 10000}}, ["required_count", "closed_count", "coverage_basis_points"])
    confirmed_props = {"package_id": id_string(), "package_status": {"const": "READY_FOR_COMPILATION"}, "project_lock_id": id_string(), "contract_catalog_digest": digest(), "domain_pack_lock_ids": array(id_string(), max_items=32, min_items=1), "scope_id": id_string(), "scope_approval_id": id_string(), "competency_question_set_id": id_string(), "competency_question_coverage_report_id": id_string(), "kg_ir_dataset_ids": array(id_string(), max_items=128, min_items=1), "baseline_snapshot_id": id_string(), "terminology_catalog_id": id_string(), "term_alignment_set_id": id_string(), "field_mapping_candidate_set_id": id_string(), "source_proposal_id": id_string(), "source_proposal_digest": digest(), "formal_prevalidation_report_id": id_string(), "review_policy_id": id_string(), "review_decision_log_id": id_string(), "review_semantic_hash": digest(), "confirmed_tbox": array(candidate(), max_items=100000), "confirmed_mapping": array(candidate(), max_items=100000), "confirmed_abox": array(candidate(), max_items=100000), "confirmed_shacl": array(candidate(), max_items=100000), "rejected_candidates": array(id_string(), max_items=100000), "deferred_candidates": array(id_string(), max_items=100000), "resolved_conflicts": array(id_string(), max_items=100000), "evidence_closure": closure, "dependency_closure": closure, "compiler_requirements": closed({"input_contract": {"const": "ontology-confirmed-modeling-package/1.0.0"}, "minimum_compiler_version": string(max_length=64), "required_validation_profiles": array(string(max_length=256), max_items=64)}, ["input_contract", "minimum_compiler_version", "required_validation_profiles"]), "artifact_manifest": closed({"artifact_ids": array(id_string(), max_items=100000), "artifact_sha256": digest()}, ["artifact_ids", "artifact_sha256"]), "content_digest": digest()}
    confirmed = manifest_schema("ontology-confirmed-modeling-package", "KG_MNP_ONTOLOGY_CONFIRMED_MODELING_PACKAGE", confirmed_props, list(confirmed_props))
    result[MODELING_ROOT / "ontology_confirmed_modeling_package.schema.json"] = confirmed

    limits_names = ["max_kgir_datasets", "max_kgir_items", "max_terms", "max_alignment_candidates_per_term", "max_total_candidates", "max_candidate_dependencies", "max_conflicts", "max_definition_characters", "max_rationale_characters", "max_model_response_bytes", "max_model_json_depth", "max_review_actions", "max_baseline_triples", "max_baseline_import_depth"]
    run_props = {"modeling_run_id": id_string(), "project_lock_id": id_string(), "modeling_input_bundle_id": id_string(), "proposal_id": {"oneOf": [id_string(), {"type": "null"}]}, "review_queue_id": {"oneOf": [id_string(), {"type": "null"}]}, "package_id": {"oneOf": [id_string(), {"type": "null"}]}, "limits": closed({name: {"type": "integer", "minimum": 1, "maximum": 1000000000} for name in limits_names}, limits_names), "status": {"enum": ["INPUT_READY", "PROPOSED", "PREVALIDATED", "UNDER_REVIEW", "READY_FOR_COMPILATION", "FAILED"]}, "content_digest": digest()}
    run = manifest_schema("ontology-modeling-run", "KG_MNP_ONTOLOGY_MODELING_RUN", run_props, list(run_props))
    result[MODELING_ROOT / "ontology_modeling_run.schema.json"] = run

    plugin_common = {
        "$schema": DRAFT, "$id": f"{TOOLCHAIN_BASE}/plugin-common/1.1", "title": "KG-MNP Plugin Common 1.1",
        "$defs": {
            "pluginId": string(max_length=128, pattern="^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"),
            "pluginApiVersion": {"const": "1.1.0"}, "pluginKind": {"const": "modeling-provider"},
            "capabilityId": {"enum": ["terminology-alignment", "baseline-reuse", "tbox-proposal", "field-mapping-proposal", "abox-proposal", "shacl-proposal", "repair-suggestion"]},
            "safeRelativePath": string(max_length=1024, pattern="^(?![A-Za-z]:|/|\\\\|.*(?:^|/)\\.\\.(?:/|$)).+$"),
        },
        **closed({}, []),
    }
    result[TOOLCHAIN_ROOT / "plugin_common_v1_1.schema.json"] = plugin_common

    plugin_manifest_props = {
        "manifest_kind": {"const": "KG_MNP_PLUGIN"}, "schema_version": {"const": "1.1.0"}, "plugin_api_version": {"const": "1.1.0"},
        "plugin_id": {"$ref": f"{TOOLCHAIN_BASE}/plugin-common/1.1#/$defs/pluginId"}, "plugin_version": {"const": "1.0.0"},
        "display_name": string(max_length=256), "description": string(max_length=4096),
        "distribution": closed({"name": string(max_length=256), "required_version": {"const": "0.4.0"}}, ["name", "required_version"]),
        "entry_point": closed({"group": {"const": "kg_mnp.plugins"}, "name": {"$ref": f"{TOOLCHAIN_BASE}/plugin-common/1.1#/$defs/pluginId"}, "object": string(max_length=512, pattern="^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_.]*$")}, ["group", "name", "object"]),
        "plugin_kinds": {"type": "array", "items": {"const": "modeling-provider"}, "minItems": 1, "maxItems": 1, "uniqueItems": True},
        "capabilities": array({"$ref": f"{TOOLCHAIN_BASE}/plugin-common/1.1#/$defs/capabilityId"}, max_items=7, min_items=1),
        "media_types": {"type": "array", "maxItems": 0}, "priority": {"type": "integer", "minimum": 0, "maximum": 1000},
        "determinism": {"enum": ["DETERMINISTIC", "RECORDED_BYTES", "HUMAN_AUTHORED"]}, "side_effects": {"type": "array", "items": {"enum": ["PURE", "READ_RECORDED_INPUT"]}, "minItems": 1, "maxItems": 2, "uniqueItems": True},
        "implementation_files": array({"$ref": f"{TOOLCHAIN_BASE}/plugin-common/1.1#/$defs/safeRelativePath"}, max_items=64, min_items=1),
        "configuration_contract": {"type": "null"}, "requirements": closed({"python": string(max_length=64), "optional_dependencies": {"type": "array", "maxItems": 0}}, ["python", "optional_dependencies"]),
        "extensions": closed({}, []), "input_contracts": array(string(max_length=128), max_items=32, min_items=1), "output_contracts": array(string(max_length=128), max_items=32, min_items=1),
        "authority_level": {"const": "PROPOSAL_ONLY"}, "network_policy": {"const": "DENY"},
    }
    plugin_manifest = {"$schema": DRAFT, "$id": f"{TOOLCHAIN_BASE}/plugin-manifest/1.1", "title": "KG-MNP PluginManifest 1.1", **closed(plugin_manifest_props, list(plugin_manifest_props))}
    result[TOOLCHAIN_ROOT / "plugin_manifest_v1_1.schema.json"] = plugin_manifest

    snapshot_props = {"manifest_kind": {"const": "KG_MNP_PLUGIN_SNAPSHOT"}, "schema_version": {"const": "1.1.0"}, "snapshot_id": id_string(), "plugin_id": {"$ref": f"{TOOLCHAIN_BASE}/plugin-common/1.1#/$defs/pluginId"}, "plugin_version": {"const": "1.0.0"}, "plugin_api_version": {"const": "1.1.0"}, "distribution_name": string(max_length=256), "distribution_version": {"const": "0.4.0"}, "entry_point": string(max_length=512), "manifest_sha256": digest(), "manifest_semantic_sha256": digest(), "implementation_digest": digest(), "configuration_semantic_sha256": digest(), "capabilities": array({"$ref": f"{TOOLCHAIN_BASE}/plugin-common/1.1#/$defs/capabilityId"}, max_items=7, min_items=1), "determinism": {"enum": ["DETERMINISTIC", "RECORDED_BYTES", "HUMAN_AUTHORED"]}, "side_effects": {"type": "array", "items": {"enum": ["PURE", "READ_RECORDED_INPUT"]}, "minItems": 1, "maxItems": 2, "uniqueItems": True}, "authority_level": {"const": "PROPOSAL_ONLY"}, "network_policy": {"const": "DENY"}, "input_contracts": array(string(max_length=128), max_items=32, min_items=1), "output_contracts": array(string(max_length=128), max_items=32, min_items=1)}
    plugin_snapshot = {"$schema": DRAFT, "$id": f"{TOOLCHAIN_BASE}/plugin-snapshot/1.1", "title": "KG-MNP PluginSnapshot 1.1", **closed(snapshot_props, list(snapshot_props))}
    result[TOOLCHAIN_ROOT / "plugin_snapshot_v1_1.schema.json"] = plugin_snapshot
    return result


def entries(documents: dict[Path, dict[str, Any]]) -> list[dict[str, Any]]:
    authority = {
        "ontology-modeling-common": "descriptive", "ontology-scope": "control", "ontology-scope-approval": "control",
        "competency-question-set": "control", "competency-question-coverage-report": "descriptive", "ontology-baseline-snapshot": "descriptive",
        "terminology-catalog": "descriptive", "term-alignment-set": "proposal", "field-mapping-candidate-set": "proposal",
        "modeling-input-bundle": "control", "modeling-provider-request": "control", "modeling-provider-response": "proposal",
        "model-invocation-record": "descriptive", "ontology-candidate-set": "proposal", "ontology-modeling-proposal": "proposal",
        "formal-prevalidation-report": "control", "ontology-review-policy": "control", "ontology-review-queue": "control",
        "ontology-review-action": "control", "ontology-review-decision-log": "control", "ontology-confirmed-modeling-package": "confirmed-input",
        "ontology-modeling-run": "control", "plugin-common-v1-1": "descriptive", "plugin-manifest-v1-1": "control", "plugin-snapshot-v1-1": "lock",
    }
    rows = []
    for path, schema in documents.items():
        stem = path.name.removesuffix(".schema.json").replace("_", "-")
        name = stem
        if stem in {"plugin-common-v1-1", "plugin-manifest-v1-1", "plugin-snapshot-v1-1"}:
            version = "1.1.0"
            scope = "toolchain"
        else:
            version = "1.0.0"
            scope = "modeling"
        rows.append({
            "name": name, "version": version, "schema_id": schema["$id"],
            "resource_path": path.relative_to(SCHEMA_ROOT.parent).as_posix(), "scope": scope,
            "stability": "experimental", "authority_level": authority[name],
            "sha256": bytes_sha256(deterministic_json_bytes(schema)),
        })
    return sorted(rows, key=lambda row: (row["scope"], row["name"], row["version"]))


def expected_catalog(documents: dict[Path, dict[str, Any]]) -> dict[str, Any]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    names = {entry["name"] for entry in entries(documents)}
    retained = [entry for entry in catalog["contracts"] if entry["name"] not in names]
    updated = copy.deepcopy(catalog)
    updated["contracts"] = sorted([*retained, *entries(documents)], key=lambda row: (row["scope"], row["name"], row["version"]))
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    documents = schemas()
    expected = {path: deterministic_json_bytes(schema) for path, schema in documents.items()}
    catalog_bytes = deterministic_json_bytes(expected_catalog(documents))
    if args.check:
        stale = [str(path.relative_to(ROOT)) for path, content in expected.items() if not path.is_file() or path.read_bytes() != content]
        if CATALOG_PATH.read_bytes() != catalog_bytes:
            stale.append(str(CATALOG_PATH.relative_to(ROOT)))
        if stale:
            raise SystemExit("Prompt 4 generated files are stale: " + ", ".join(stale))
        print(f"Prompt 4 contract family is current ({len(documents)} schemas).")
        return 0
    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    CATALOG_PATH.write_bytes(catalog_bytes)
    print(f"Generated {len(documents)} Prompt 4 schemas and Catalog entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
