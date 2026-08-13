"""Authority-mode-specific identifiers for production and test-only governance."""

from __future__ import annotations

from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash, stable_urn

from .authority_binding import CONTROLLED_HARNESS_AUTHORITY_TYPE

CONTROLLED_FIXTURE_NAMESPACE = "urn:kg-mnp:test-fixture:phase04:"


def governance_urn(kind: str, value: Any, authority_type: str) -> str:
    if authority_type == CONTROLLED_HARNESS_AUTHORITY_TYPE:
        return f"{CONTROLLED_FIXTURE_NAMESPACE}{kind}:{semantic_hash(value)}"
    return stable_urn(kind, value)
