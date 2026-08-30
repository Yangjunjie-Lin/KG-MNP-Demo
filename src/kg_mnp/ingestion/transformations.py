"""Core-owned deterministic TransformationRecord generation."""

from __future__ import annotations

from typing import Any

from kg_mnp.contracts.canonical import semantic_hash

from .contracts import finalize_document


def transformation_record(
    transformation_type: str,
    original_value: Any,
    normalized_value: Any,
) -> dict[str, Any]:
    loss = "NONE" if transformation_type in {"safe-string-preservation", "decimal-string-preservation"} else "REPRESENTATION_ONLY"
    return finalize_document(
        {
            "manifest_kind": "KG_MNP_TRANSFORMATION_RECORD",
            "schema_version": "1.0.0",
            "transformation_type": transformation_type,
            "implementation": "kg-mnp-generic-normalizer-1.0.0",
            "configuration_semantic_sha256": semantic_hash({}),
            "input_sha256": semantic_hash(original_value),
            "output_sha256": semantic_hash(normalized_value),
            "reversible": True,
            "loss_class": loss,
            "description": f"Deterministic {transformation_type} transformation.",
        },
        contract="transformation-record",
        id_field="transformation_id",
        urn_kind="transformation",
    )
