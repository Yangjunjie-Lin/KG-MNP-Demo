from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..modeling.canonical_json import semantic_hash


def publication_semantic_content(value: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "cleaned_partial_data_hash",
        "modeling_proposal_id",
        "modeling_proposal_hash",
        "review_decision_log_id",
        "review_decision_log_hash",
        "confirmed_modeling_package_id",
        "confirmed_modeling_package_hash",
        "compilation_id",
        "compilation_semantic_hash",
        "graphdb_publication_id",
        "graphdb_publication_semantic_hash",
        "visualization_id",
        "visualization_semantic_hash",
        "ontology_baseline_id",
        "ontology_version",
        "ontology_release_source_hash",
        "artifact_manifest",
        "webvowl_upstream_commit",
        "owl2vowl_upstream_commit",
    )
    return {key: value[key] for key in fields}


def publication_semantic_hash(value: Mapping[str, Any]) -> str:
    return semantic_hash(publication_semantic_content(value))


def publication_id(value: Mapping[str, Any] | str) -> str:
    digest = value if isinstance(value, str) else publication_semantic_hash(value)
    return f"urn:kg-mnp:e2e-publication:{digest}"
