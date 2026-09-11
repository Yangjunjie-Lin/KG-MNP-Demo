"""KG-IR field mapping observations without raw-source reparsing."""

from __future__ import annotations

from typing import Any

from zhigou_toolchain.contracts.canonical import stable_urn
from zhigou_toolchain.contracts.registry import validate_contract

from .artifacts import finalize_document, verify_document
from .errors import ModelingControlError


def table_identity(item: dict[str, Any], evidence: dict[str, dict[str, Any]]) -> tuple[str, str, str | int | None]:
    """Coordinates are scoped to a Source, format and exact sheet/Word table."""
    locations = set()
    for reference in item["evidence_refs"]:
        record = evidence.get(reference)
        if record is None or record["source_id"] not in item["source_ids"]:
            raise ModelingControlError("table cell evidence does not bind its Source")
        locator = record["locator"]
        kind = locator["locator_kind"]
        if kind not in {"delimited-cell", "spreadsheet-cell", "document-table-cell"}:
            raise ModelingControlError("table cell requires an exact table locator")
        if any(locator.get(axis) != item["payload"][axis] for axis in ("row", "column")):
            raise ModelingControlError("table cell coordinate differs from its evidence")
        selector = locator.get("sheet") if kind == "spreadsheet-cell" else locator.get("table_index")
        if kind == "spreadsheet-cell" and not isinstance(selector, str):
            raise ModelingControlError("table cell requires an exact sheet")
        if kind == "document-table-cell" and (type(selector) is not int or selector < 0):
            raise ModelingControlError("table cell requires an exact Word table index")
        locations.add((record["source_id"], kind, selector))
    if len(locations) != 1 or len(item["source_ids"]) != 1:
        raise ModelingControlError("table cell has ambiguous Source or sheet authority")
    return next(iter(locations))


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
            if item["element_kind"] == "DATA_PROPERTY"
        }
        if baseline is not None
        else None
    )
    mappings: list[dict[str, Any]] = []
    dataset_ids: list[str] = []
    for dataset in kg_ir_datasets:
        dataset_ids.append(dataset["dataset_id"])
        evidence = {record["evidence_id"]: record for record in dataset["evidence_records"]}
        table_headers = {}
        for item in dataset["items"]:
            if item["item_kind"] == "table-cell" and item["payload"]["row"] == 1:
                key = (table_identity(item, evidence), item["payload"]["column"])
                if key in table_headers and table_headers[key] != item:
                    raise ModelingControlError("ambiguous table header at the same Source/sheet/column")
                table_headers[key] = item
        for item in dataset["items"]:
            if item["item_kind"] == "scalar-field":
                field_name = item["payload"]["field_name"]
                term_source_ref = item["item_id"]
                value = item["payload"]["value"]
            elif item["item_kind"] == "table-cell" and item["payload"]["row"] > 1:
                header = table_headers.get((table_identity(item, evidence), item["payload"]["column"]))
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
            # Lexical ranking alone is not a semantic identity decision. Tied
            # targets and merely similar spellings remain explicit user work.
            best = {t["target_iri"] for t in targets if t["score_basis_points"] == targets[0]["score_basis_points"]} if targets else set()
            target = next(iter(best)) if len(best) == 1 and targets[0]["score_basis_points"] >= 9000 else None
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
