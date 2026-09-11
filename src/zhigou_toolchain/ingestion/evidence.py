"""Core-authoritative EvidenceRecord binding and closure validation."""

from __future__ import annotations

from typing import Any

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.contracts.registry import validate_contract
from zhigou_toolchain.plugins.models import NormalizedUnit, ResourceLimits

from .contracts import finalize_document, verify_finalized_document
from .errors import SourceTamperedError
from .models import EvidenceBundle
from .transformations import transformation_record
from .validation import extract_locator_value, validate_locator


def _metadata(unit: NormalizedUnit) -> dict[str, Any]:
    return dict(unit.metadata)


def build_evidence_bundle(
    *,
    source: dict[str, Any],
    content: bytes,
    units: tuple[NormalizedUnit, ...],
    parser_snapshot_id: str,
) -> EvidenceBundle:
    transformations: dict[str, dict[str, Any]] = {}
    evidence: list[dict[str, Any]] = []
    whole = finalize_document(
        {
            "manifest_kind": "KG_MNP_EVIDENCE_RECORD",
            "schema_version": "1.0.0",
            "source_id": source["source_id"],
            "source_content_sha256": source["content_sha256"],
            "locator": {"locator_kind": "whole-source"},
            "observed_content_sha256": source["content_sha256"],
            "observed_content_media_type": source["detected_media_type"],
            "observed_value": source["content_sha256"],
            "plugin_snapshot_id": parser_snapshot_id,
            "transformation_ids": [],
            "quality_flags": [],
        },
        contract="evidence-record",
        id_field="evidence_id",
        urn_kind="evidence",
    )
    evidence.append(whole)
    for unit in units:
        transformation_ids = []
        for transformation_type in unit.transformations:
            record = transformation_record(
                transformation_type, unit.original_value, unit.normalized_value
            )
            transformations[record["transformation_id"]] = record
            transformation_ids.append(record["transformation_id"])
        validate_locator(unit.locator)
        observed = unit.original_value
        record = finalize_document(
            {
                "manifest_kind": "KG_MNP_EVIDENCE_RECORD",
                "schema_version": "1.0.0",
                "source_id": source["source_id"],
                "source_content_sha256": source["content_sha256"],
                "locator": unit.locator,
                "observed_content_sha256": semantic_hash(observed),
                "observed_content_media_type": unit.media_type,
                "observed_value": observed,
                "plugin_snapshot_id": parser_snapshot_id,
                "transformation_ids": transformation_ids,
                "quality_flags": sorted(set(unit.quality_flags)),
            },
            contract="evidence-record",
            id_field="evidence_id",
            urn_kind="evidence",
        )
        evidence.append(record)
    return EvidenceBundle(
        evidence_records=tuple(sorted(evidence, key=lambda item: item["evidence_id"])),
        transformation_records=tuple(
            transformations[key] for key in sorted(transformations)
        ),
    )


def verify_evidence_closure(
    *,
    records: tuple[dict[str, Any], ...],
    transformations: tuple[dict[str, Any], ...],
    snapshots: tuple[dict[str, Any], ...],
    sources: dict[str, tuple[dict[str, Any], bytes]],
    limits: ResourceLimits,
) -> None:
    transformation_ids = {item["transformation_id"] for item in transformations}
    snapshot_ids = {item["snapshot_id"] for item in snapshots}
    for record in records:
        verify_finalized_document(record, contract="evidence-record", id_field="evidence_id", urn_kind="evidence")
        try:
            source, content = sources[record["source_id"]]
        except KeyError as exc:
            raise SourceTamperedError("EvidenceRecord has no SourceAsset closure") from exc
        if source["content_sha256"] != record["source_content_sha256"]:
            raise SourceTamperedError("EvidenceRecord source hash mismatch")
        if record["plugin_snapshot_id"] not in snapshot_ids:
            raise SourceTamperedError("EvidenceRecord PluginSnapshot closure incomplete")
        if not set(record["transformation_ids"]).issubset(transformation_ids):
            raise SourceTamperedError("EvidenceRecord transformation closure incomplete")
        extracted = extract_locator_value(
            content=content,
            media_type=source["detected_media_type"],
            locator=record["locator"],
            limits=limits,
        )
        if record["locator"]["locator_kind"] == "whole-source":
            expected_hash = source["content_sha256"]
        else:
            if (
                isinstance(record["observed_value"], dict)
                and set(record["observed_value"]) == {"decimal"}
                and not (isinstance(extracted, dict) and set(extracted) == {"decimal"})
            ):
                extracted = {"decimal": str(extracted)}
            expected_hash = semantic_hash(extracted)
        if record["observed_content_sha256"] != expected_hash:
            raise SourceTamperedError("EvidenceRecord locator re-verification failed")
        validate_contract("evidence-record", record)
