from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from ..modeling.canonical_json import semantic_hash


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def vowl_semantic_content(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "header": value.get("header", {}),
        "namespace": value.get("namespace", []),
        "class": value.get("class", []),
        "classAttribute": value.get("classAttribute", []),
        "property": value.get("property", []),
        "propertyAttribute": value.get("propertyAttribute", []),
        "individual": value.get("individual", []),
    }


def normalized_vowl_semantic_hash(value: Mapping[str, Any]) -> str:
    return semantic_hash(vowl_semantic_content(value))


def visualization_semantic_content(value: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "ontology_baseline_id",
        "ontology_version",
        "ontology_release_source_hash",
        "tbox_source_semantic_hash",
        "webvowl_upstream_commit",
        "owl2vowl_upstream_commit",
        "normalized_vowl_semantic_hash",
        "class_count",
        "object_property_count",
        "datatype_property_count",
        "missing_required_term_count",
        "unexpected_project_term_count",
        "representation_loss_report_hash",
    )
    return {key: value[key] for key in fields}


def visualization_semantic_hash(value: Mapping[str, Any]) -> str:
    return semantic_hash(visualization_semantic_content(value))


def visualization_id(value: Mapping[str, Any] | str) -> str:
    digest = value if isinstance(value, str) else visualization_semantic_hash(value)
    if len(digest) != 64:
        raise ValueError("visualization hash must be SHA-256")
    return f"urn:kg-mnp:visualization:{digest}"
