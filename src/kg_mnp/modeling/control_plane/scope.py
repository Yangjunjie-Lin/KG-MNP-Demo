"""Approved ontology modeling scope construction and validation."""

from __future__ import annotations

from typing import Any

from kg_mnp.contracts.registry import validate_contract

from .artifacts import finalize_document, verify_document
from .errors import ScopeInvalidError
from .security import RESERVED_NAMESPACES, assert_safe_json, validate_iri

MODEL_INTENTS = frozenset({"CREATE_NEW_ONTOLOGY", "EXTEND_BASELINE", "ALIGN_TO_BASELINE", "INSTANCE_POPULATION", "MAPPING_ONLY", "MIXED_MODELING"})
TARGET_ARTIFACTS = frozenset({"TBOX", "ABOX", "MAPPING", "SHACL", "TERMINOLOGY"})
DEFAULT_PROHIBITED = (
    "AUTHORITATIVE_RDF_WRITE", "ONTOLOGY_PUBLICATION", "GRAPHDB_WRITE", "AUTO_APPROVAL",
    "REMOTE_IMPORT_FETCH", "LIVE_MODEL_INVOCATION",
)


def build_scope(
    *,
    project_id: str,
    project_lock_id: str,
    domain_pack_lock_ids: list[str] | tuple[str, ...],
    kg_ir_dataset_ids: list[str] | tuple[str, ...],
    modeling_intent: str,
    domain_description: str,
    target_object_families: list[str] | tuple[str, ...],
    in_scope: list[str] | tuple[str, ...],
    out_of_scope: list[str] | tuple[str, ...],
    target_artifacts: list[str] | tuple[str, ...],
    default_namespace: str,
    allowed_new_namespaces: list[str] | tuple[str, ...] = (),
    reusable_namespaces: list[str] | tuple[str, ...] = (),
    allowed_languages: list[str] | tuple[str, ...] = ("en",),
    iri_strategy: str = "HUMAN_READABLE_SLUG",
    baseline_policy: str = "REUSE_FIRST",
    competency_question_set_id: str | None = None,
    acceptance_gates: list[str] | tuple[str, ...] = ("FORMAL_PREVALIDATION", "HUMAN_REVIEW"),
) -> dict[str, Any]:
    if modeling_intent not in MODEL_INTENTS:
        raise ScopeInvalidError("unsupported modeling intent")
    if not target_artifacts or set(target_artifacts) - TARGET_ARTIFACTS:
        raise ScopeInvalidError("invalid target artifacts")
    if set(in_scope) & set(out_of_scope):
        raise ScopeInvalidError("in-scope and out-of-scope entries conflict")
    namespaces = tuple(sorted({default_namespace, *allowed_new_namespaces}))
    for namespace in namespaces:
        validate_iri(namespace)
        if any(namespace.startswith(item) for item in RESERVED_NAMESPACES):
            raise ScopeInvalidError("reserved standard namespace cannot authorize new IRIs")
    for namespace in reusable_namespaces:
        validate_iri(namespace)
    core = {
        "manifest_kind": "KG_MNP_ONTOLOGY_SCOPE",
        "schema_version": "1.0.0",
        "project_id": project_id,
        "project_lock_id": project_lock_id,
        "domain_pack_locks": sorted(set(domain_pack_lock_ids)),
        "kg_ir_dataset_ids": sorted(set(kg_ir_dataset_ids)),
        "modeling_intent": modeling_intent,
        "domain_description": domain_description,
        "target_object_families": sorted(set(target_object_families)),
        "in_scope": sorted(set(in_scope)),
        "out_of_scope": sorted(set(out_of_scope)),
        "target_artifacts": sorted(set(target_artifacts)),
        "namespace_policy": {
            "default_namespace": default_namespace,
            "allowed_new_namespaces": list(namespaces),
            "reusable_namespaces": sorted(set(reusable_namespaces)),
            "reserved_namespaces": list(RESERVED_NAMESPACES),
            "allowed_iri_schemes": ["https", "urn"],
            "external_iri_policy": "ALLOW_LISTED" if reusable_namespaces else "DENY",
        },
        "language_policy": {"default_language": allowed_languages[0], "allowed_languages": sorted(set(allowed_languages))},
        "iri_minting_policy": {"strategy": iri_strategy, "slug_pattern": "^[a-z][a-z0-9-]*$", "allow_random_uuid": False},
        "baseline_policy": baseline_policy,
        "competency_question_set_id": competency_question_set_id,
        "acceptance_gates": sorted(set(acceptance_gates)),
        "prohibited_operations": list(DEFAULT_PROHIBITED),
    }
    assert_safe_json(core)
    scope = finalize_document(core, id_field="scope_id", urn_kind="ontology-scope")
    validate_contract("ontology-scope", scope)
    return scope


def verify_scope(scope: dict[str, Any], *, project_lock_id: str | None = None) -> None:
    validate_contract("ontology-scope", scope)
    verify_document(scope, id_field="scope_id", urn_kind="ontology-scope")
    if project_lock_id is not None and scope["project_lock_id"] != project_lock_id:
        raise ScopeInvalidError("scope is bound to another or stale Project Lock")
