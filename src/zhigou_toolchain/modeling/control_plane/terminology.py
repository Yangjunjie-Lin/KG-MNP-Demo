"""Deterministic multi-source terminology catalog."""

from __future__ import annotations

import unicodedata
from typing import Any

from zhigou_toolchain.contracts.canonical import stable_urn
from zhigou_toolchain.contracts.registry import validate_contract

from .artifacts import finalize_document, verify_document
from .baseline import verify_baseline_snapshot
from .limits import ModelingLimits
from .scope import verify_scope


def normalize_term(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _term(
    lexical: str,
    *,
    language: str | None,
    source_type: str,
    source_ref: str,
    evidence_refs: list[str] | tuple[str, ...] = (),
    candidate_iris: list[str] | tuple[str, ...] = (),
    definition: str | None = None,
    aliases: list[str] | tuple[str, ...] = (),
    status: str = "PROPOSED",
) -> dict[str, Any]:
    semantic = {"lexical_form": lexical, "language": language, "source_type": source_type, "source_ref": source_ref}
    return {
        "term_id": stable_urn("terminology-term", semantic), "lexical_form": lexical,
        "normalized_form": normalize_term(lexical), "language": language, "source_type": source_type,
        "source_ref": source_ref, "evidence_refs": sorted(set(evidence_refs)),
        "candidate_iris": sorted(set(candidate_iris)), "definition": definition,
        "aliases": sorted(set(aliases)), "status": status,
    }


def build_terminology_catalog(
    *,
    scope: dict[str, Any],
    baseline: dict[str, Any],
    kg_ir_datasets: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    domain_terms: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    human_terms: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    limits: ModelingLimits | None = None,
) -> dict[str, Any]:
    verify_scope(scope)
    verify_baseline_snapshot(baseline)
    effective_limits = limits or ModelingLimits()
    terms: dict[str, dict[str, Any]] = {}
    for element in baseline["elements"]:
        for label in element["labels"]:
            item = _term(label["value"], language=label["language"], source_type="ONTOLOGY_BASELINE", source_ref=element["element_id"], candidate_iris=[element["iri"]], definition=element["definition"])
            terms[item["term_id"]] = item
    for value in scope["target_object_families"]:
        item = _term(value, language=scope["language_policy"]["default_language"], source_type="APPROVED_SCOPE", source_ref=scope["scope_id"])
        terms[item["term_id"]] = item
    dataset_ids = []
    for dataset in kg_ir_datasets:
        dataset_ids.append(dataset["dataset_id"])
        for kg_item in dataset["items"]:
            payload = kg_item["payload"]
            lexical_values: list[str] = []
            if kg_item["item_kind"] == "scalar-field":
                lexical_values.append(payload["field_name"])
            elif kg_item["item_kind"] == "table-cell" and payload["row"] == 1:
                lexical_values.append(payload["value"]["normalized_lexical_value"])
            elif kg_item["item_kind"] == "structured-record":
                lexical_values.append(payload["record_label"])
            elif kg_item["item_kind"] == "text-block" and payload.get("block_kind") == "heading":
                lexical_values.append(payload["text"])
            for lexical in lexical_values:
                item = _term(lexical, language=None, source_type="KG_IR", source_ref=kg_item["item_id"], evidence_refs=kg_item["evidence_refs"])
                terms[item["term_id"]] = item
    for source_type, rows, status in (("DOMAIN_PACK", domain_terms, "PROPOSED"), ("HUMAN_AUTHORED", human_terms, "HUMAN_AUTHORED")):
        for row in rows:
            item = _term(row["lexical_form"], language=row.get("language"), source_type=source_type, source_ref=row["source_ref"], evidence_refs=row.get("evidence_refs", []), candidate_iris=row.get("candidate_iris", []), definition=row.get("definition"), aliases=row.get("aliases", []), status=status)
            terms[item["term_id"]] = item
    if len(terms) > effective_limits.max_terms:
        raise ValueError("terminology limit exceeded")
    core = {
        "manifest_kind": "KG_MNP_TERMINOLOGY_CATALOG", "schema_version": "1.0.0",
        "project_lock_id": scope["project_lock_id"], "scope_id": scope["scope_id"],
        "baseline_snapshot_id": baseline["baseline_snapshot_id"], "kg_ir_dataset_ids": sorted(dataset_ids),
        "terms": sorted(terms.values(), key=lambda item: item["term_id"]),
    }
    catalog = finalize_document(core, id_field="terminology_catalog_id", urn_kind="terminology-catalog")
    validate_contract("terminology-catalog", catalog)
    return catalog


def verify_terminology_catalog(value: dict[str, Any]) -> None:
    validate_contract("terminology-catalog", value)
    verify_document(value, id_field="terminology_catalog_id", urn_kind="terminology-catalog")
