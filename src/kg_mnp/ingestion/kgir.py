"""Evidence-bound KG-IR builder; no ontology or business-object semantics."""

from __future__ import annotations

from typing import Any

from .contracts import finalize_document, verify_finalized_document
from .errors import IngestionError

PROHIBITED_ITEM_KINDS = {
    "ontology-class", "ontology-property", "ontology-relation",
    "ontology-instance", "business-object", "confirmed-fact",
}


def _lexical(value: Any) -> tuple[str, str | None, str | None, str]:
    if value is None:
        return "null", None, None, "EXPLICIT_NULL"
    if isinstance(value, bool):
        lexical = "true" if value else "false"
        return "boolean", lexical, lexical, "NOT_NULL"
    if isinstance(value, int):
        lexical = str(value)
        return "integer", lexical, lexical, "NOT_NULL"
    if isinstance(value, dict) and set(value) == {"decimal"}:
        lexical = value["decimal"]
        return "decimal", lexical, lexical, "NOT_NULL"
    lexical = str(value)
    return "string", lexical, lexical, "NOT_NULL"


def _scalar_payload(original_value: Any, normalized_value: Any) -> dict[str, Any]:
    datatype, _ignored, normalized, null_state = _lexical(normalized_value)
    _original_datatype, original, _ignored_normalized, _original_null = _lexical(original_value)
    return {
        "datatype": datatype,
        "original_lexical_value": original,
        "normalized_lexical_value": normalized,
        "null_state": null_state,
    }


def _payload(unit) -> tuple[str, dict[str, Any]]:
    metadata = dict(unit.metadata)
    if unit.unit_kind == "text-block":
        return "text-block", {
            "text": str(unit.normalized_value),
            "block_kind": metadata.get("block_kind", "plain"),
        }
    if unit.unit_kind == "scalar-field":
        return "scalar-field", {
            "field_name": str(metadata.get("field_name", "$")),
            "value": _scalar_payload(unit.original_value, unit.normalized_value),
        }
    if unit.unit_kind == "table-cell":
        return "table-cell", {
            "row": int(metadata["row"]),
            "column": int(metadata["column"]),
            "value": _scalar_payload(unit.original_value, unit.normalized_value),
        }
    if unit.unit_kind in {"image-metadata", "audio-metadata", "document-metadata"}:
        entries = [
            {"name": key, "value": value}
            for key, value in sorted(metadata.items())
        ]
        return unit.unit_kind, {"entries": entries}
    raise IngestionError(f"unsupported normalized KG-IR unit kind: {unit.unit_kind}")


def build_items_for_source(
    *,
    source: dict[str, Any],
    units: tuple,
    evidence_records: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    whole = next(
        item for item in evidence_records
        if item["source_id"] == source["source_id"] and item["locator"]["locator_kind"] == "whole-source"
    )
    root = finalize_document(
        {
            "manifest_kind": "KG_MNP_KG_IR_ITEM",
            "schema_version": "1.0.0",
            "item_kind": "document",
            "source_ids": [source["source_id"]],
            "parent_item_id": None,
            "ordinal": 0,
            "payload": {"media_type": source["detected_media_type"], "title": None},
            "evidence_refs": [whole["evidence_id"]],
            "transformation_refs": [],
            "quality_flags": list(whole["quality_flags"]),
        },
        contract="kg-ir-item",
        id_field="item_id",
        urn_kind="kg-ir-item",
    )
    by_locator = {
        __import__("json").dumps(item["locator"], sort_keys=True, separators=(",", ":")): item
        for item in evidence_records if item["source_id"] == source["source_id"]
    }
    items = [root]
    for unit in units:
        key = __import__("json").dumps(unit.locator, sort_keys=True, separators=(",", ":"))
        evidence = by_locator[key]
        item_kind, payload = _payload(unit)
        item = finalize_document(
            {
                "manifest_kind": "KG_MNP_KG_IR_ITEM",
                "schema_version": "1.0.0",
                "item_kind": item_kind,
                "source_ids": [source["source_id"]],
                "parent_item_id": root["item_id"],
                "ordinal": unit.ordinal + 1,
                "payload": payload,
                "evidence_refs": [evidence["evidence_id"]],
                "transformation_refs": list(evidence["transformation_ids"]),
                "quality_flags": list(evidence["quality_flags"]),
            },
            contract="kg-ir-item",
            id_field="item_id",
            urn_kind="kg-ir-item",
        )
        items.append(item)
    return tuple(items)


def build_dataset(
    *,
    project_lock_id: str,
    source_batch_id: str,
    ingestion_plan_id: str,
    items: tuple[dict[str, Any], ...],
    evidence_records: tuple[dict[str, Any], ...],
    transformation_records: tuple[dict[str, Any], ...],
    plugin_snapshots: tuple[dict[str, Any], ...],
    artifact_manifest: dict[str, Any],
    quality_report_id: str,
) -> dict[str, Any]:
    dataset = finalize_document(
        {
            "manifest_kind": "KG_MNP_KG_IR_DATASET",
            "schema_version": "1.0.0",
            "project_lock_id": project_lock_id,
            "source_batch_id": source_batch_id,
            "ingestion_plan_id": ingestion_plan_id,
            "items": sorted(items, key=lambda item: item["item_id"]),
            "evidence_records": sorted(evidence_records, key=lambda item: item["evidence_id"]),
            "transformation_records": sorted(transformation_records, key=lambda item: item["transformation_id"]),
            "plugin_snapshots": sorted(plugin_snapshots, key=lambda item: (item["plugin_id"], item["plugin_version"])),
            "artifact_manifest": artifact_manifest,
            "quality_report_id": quality_report_id,
        },
        contract="kg-ir-dataset",
        id_field="dataset_id",
        urn_kind="kg-ir-dataset",
    )
    validate_dataset_closure(dataset)
    return dataset


def validate_dataset_closure(dataset: dict[str, Any]) -> None:
    verify_finalized_document(dataset, contract="kg-ir-dataset", id_field="dataset_id", urn_kind="kg-ir-dataset")
    item_ids = {item["item_id"] for item in dataset["items"]}
    evidence_ids = {item["evidence_id"] for item in dataset["evidence_records"]}
    transformation_ids = {item["transformation_id"] for item in dataset["transformation_records"]}
    snapshot_ids = {item["snapshot_id"] for item in dataset["plugin_snapshots"]}
    for item in dataset["items"]:
        if item["item_kind"] in PROHIBITED_ITEM_KINDS or not item["evidence_refs"]:
            raise IngestionError("KG-IR item violates evidence/modeling boundary")
        if not set(item["evidence_refs"]).issubset(evidence_ids):
            raise IngestionError("KG-IR evidence closure incomplete")
        if not set(item["transformation_refs"]).issubset(transformation_ids):
            raise IngestionError("KG-IR transformation closure incomplete")
        parent = item["parent_item_id"]
        if parent is not None and parent not in item_ids:
            raise IngestionError("KG-IR parent closure incomplete")
    for evidence in dataset["evidence_records"]:
        if evidence["plugin_snapshot_id"] not in snapshot_ids:
            raise IngestionError("KG-IR PluginSnapshot closure incomplete")
