"""TM Forum mapping helpers."""

from __future__ import annotations

from typing import Any

import yaml

from kg_mnp_demo.loader import mappings_path, source_manifest_path


def load_mappings() -> list[dict[str, Any]]:
    with open(mappings_path(), encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return list(data.get("mappings", []))


def mappings_used_for_case() -> list[dict[str, Any]]:
    """MVP cases always use the core in-MVP mappings."""
    return [
        {
            "id": m["id"],
            "source_api": m["source_api"],
            "source_path": m["source_path"],
            "target_term": m["target_term"],
            "mapping_type": m["mapping_type"],
            "review_status": m["review_status"],
        }
        for m in load_mappings()
        if m.get("in_mvp")
    ]


def load_source_manifest() -> list[dict[str, Any]]:
    with open(source_manifest_path(), encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return list(data.get("sources", []))


def validate_mapping_structure(mapping: dict[str, Any]) -> list[str]:
    required = [
        "source_api",
        "source_version",
        "source_path",
        "target_term",
        "mapping_type",
        "transformation",
        "confidence",
        "review_status",
        "notes",
    ]
    missing = [k for k in required if k not in mapping]
    errors = [f"missing field: {k}" for k in missing]
    if mapping.get("mapping_type") == "exact":
        # Allowed only if explicitly justified; currently none should be exact for TMF JSON
        pass
    return errors
