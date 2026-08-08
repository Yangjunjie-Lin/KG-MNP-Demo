from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..modeling.canonical_json import canonical_json_bytes
from .contracts import validate_webvowl_contract
from .identifiers import sha256_bytes, visualization_id, visualization_semantic_hash


def build_visualization_manifest(
    *,
    policy: Mapping[str, Any],
    source: Mapping[str, Any],
    normalized_vowl: Mapping[str, Any],
    raw_bytes: bytes,
    normalized_bytes: bytes,
    coverage: Mapping[str, Any],
    loss: Mapping[str, Any],
    tbox_verified: bool,
) -> dict[str, Any]:
    represented = [item for item in coverage["represented"] if item["represented"]]
    classes = [item for item in represented if item["term_type"] == "Class"]
    obj = [item for item in represented if item["term_type"] == "ObjectProperty"]
    data = [item for item in represented if item["term_type"] == "DatatypeProperty"]
    loss_hash = sha256_bytes(canonical_json_bytes(loss))
    provisional = {
        "contract_version": "1.0",
        "ontology_baseline_id": source["baseline"]["baseline_id"],
        "ontology_version": source["baseline"]["ontology_version"],
        "ontology_release_source_hash": source["baseline"]["release_source_hash"],
        "tbox_source_semantic_hash": source["tbox_semantic_hash"],
        "webvowl_upstream_commit": policy["webvowl"]["commit_sha"],
        "owl2vowl_upstream_commit": policy["owl2vowl"]["commit_sha"],
        "owl2vowl_version": policy["owl2vowl"]["source_version"],
        "webvowl_source_version": policy["webvowl"]["source_version"],
        "raw_converter_sha256": sha256_bytes(raw_bytes),
        "normalized_vowl_sha256": sha256_bytes(normalized_bytes),
        "normalized_vowl_semantic_hash": __import__(
            "kg_mnp_demo.webvowl.identifiers",
            fromlist=["normalized_vowl_semantic_hash"],
        ).normalized_vowl_semantic_hash(normalized_vowl),
        "class_count": len(classes),
        "object_property_count": len(obj),
        "datatype_property_count": len(data),
        "missing_required_term_count": len(coverage["missing_required_terms"]),
        "unexpected_project_term_count": len(coverage["unexpected_project_terms"]),
        "representation_loss_report_hash": loss_hash,
    }
    digest = visualization_semantic_hash(provisional)
    manifest = {
        **provisional,
        "visualization_id": visualization_id(digest),
        "visualization_semantic_hash": digest,
        "visualization_scope": "TBOX_ONLY",
        "release_status": (
            "VISUALIZATION_VALIDATED" if tbox_verified else "VISUALIZATION_UNVERIFIED"
        ),
    }
    validate_webvowl_contract("visualization-manifest", manifest)
    return manifest
