"""Prompt 5 artifact identity and public-contract helpers."""

from __future__ import annotations

import copy
from typing import Any

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.registry import validate_contract


def versioned_contract(contract: str, value: dict[str, Any]) -> str:
    if contract in {"semantic-compiler-policy", "semantic-compiler-snapshot"} and value.get("schema_version") == "1.1.0":
        return contract + "-v1-1"
    return contract


def finalize_artifact(
    value: dict[str, Any],
    *,
    id_field: str,
    urn_kind: str,
    contract: str | None = None,
) -> dict[str, Any]:
    """Bind an artifact to its semantic content without time or machine state."""

    document = copy.deepcopy(value)
    document.pop(id_field, None)
    document.pop("content_digest", None)
    digest = semantic_hash(document)
    document["content_digest"] = digest
    document[id_field] = stable_urn(urn_kind, {"content_digest": digest})
    if contract is not None:
        validate_contract(versioned_contract(contract, document), document)
    return document


def verify_artifact(
    value: dict[str, Any],
    *,
    id_field: str,
    urn_kind: str,
    contract: str,
) -> None:
    validate_contract(versioned_contract(contract, value), value)
    expected = finalize_artifact(value, id_field=id_field, urn_kind=urn_kind)
    if expected != value:
        raise ValueError(f"{id_field} or content_digest mismatch")
