"""KG-IR field mapping observations without raw-source reparsing."""

from __future__ import annotations

from typing import Any

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.contracts.registry import validate_contract

from .artifacts import finalize_document, verify_document


def build_field_mapping_candidates(
    *,
    kg_ir_datasets: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    alignments: dict[str, Any],
    terminology: dict[str, Any],
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    terms_by_source = {item["source_ref"]: item for item in terminology["terms"]}
    alignment_by_term: dict[str, list[dict[str, Any]]] = {}
    for alignment in alignments["alignments"]:
        alignment_by_term.setdefault(alignment["source_term_id"], []).append(alignment)
    allowed_property_iris = (
        {
            item["iri"]
            for item in baseline["elements"]
            if item["element_kind"] in {"DATA_PROPERTY", "OBJECT_PROPERTY"}
        }
        if baseline is not None
        else None
    )
    mappings: list[dict[str, Any]] = []
    dataset_ids: list[str] = []
    for dataset in kg_ir_datasets:
        dataset_ids.append(dataset["dataset_id"])
        table_headers = {
            item["payload"]["column"]: item
            for item in dataset["items"]
            if item["item_kind"] == "table-cell" and item["payload"]["row"] == 1
        }
        for item in dataset["items"]:
            if item["item_kind"] == "scalar-field":
                field_name = item["payload"]["field_name"]
                term_source_ref = item["item_id"]
                value = item["payload"]["value"]
            elif item["item_kind"] == "table-cell" and item["payload"]["row"] > 1:
                header = table_headers.get(item["payload"]["column"])
                if header is None:
                    continue
                field_name = header["payload"]["value"]["normalized_lexical_value"]
                term_source_ref = header["item_id"]
                value = item["payload"]["value"]
            else:
                continue
            term = terms_by_source.get(term_source_ref)
            targets = sorted(
                (
                    row
                    for row in alignment_by_term.get(term["term_id"], [])
                    if row["target_iri"]
                    and (
                        allowed_property_iris is None
                        or row["target_iri"] in allowed_property_iris
                    )
                ),
                key=lambda row: (-row["score_basis_points"], row["target_iri"]),
            ) if term else []
            target = targets[0]["target_iri"] if targets else None
            semantic = {
                "source_item_id": item["item_id"],
                "source_field_name": field_name,
                "target_property_iri": target,
            }
            mappings.append({
                "field_mapping_id": stable_urn("field-mapping-candidate", semantic),
                "source_item_id": item["item_id"], "source_field_name": field_name,
                "source_item_kind": item["item_kind"], "source_datatype": value["datatype"],
                "target_class_iri": None, "target_property_iri": target,
                "mapping_kind": "FIELD_TO_DATA_PROPERTY", "conversion_policy": "IDENTITY",
                "null_policy": "OMIT", "cardinality_observation": "observed-single-value",
                "evidence_refs": sorted(item["evidence_refs"]),
                "rationale": "KG-IR field observation and reviewed terminology alignment candidate",
                "provider_refs": [], "review_required": True,
            })
    core = {
        "manifest_kind": "KG_MNP_FIELD_MAPPING_CANDIDATE_SET", "schema_version": "1.0.0",
        "kg_ir_dataset_ids": sorted(dataset_ids), "mappings": sorted(mappings, key=lambda item: item["field_mapping_id"]),
    }
    result = finalize_document(core, id_field="field_mapping_candidate_set_id", urn_kind="field-mapping-candidate-set")
    validate_contract("field-mapping-candidate-set", result)
    return result


def verify_field_mapping_set(value: dict[str, Any]) -> None:
    validate_contract("field-mapping-candidate-set", value)
    verify_document(value, id_field="field_mapping_candidate_set_id", urn_kind="field-mapping-candidate-set")
