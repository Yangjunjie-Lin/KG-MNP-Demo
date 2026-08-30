"""Contract validation and deterministic ID/digest helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.registry import validate_contract


def finalize_document(
    value: dict[str, Any],
    *,
    contract: str,
    id_field: str,
    urn_kind: str,
) -> dict[str, Any]:
    document = deepcopy(value)
    document.pop(id_field, None)
    document.pop("content_digest", None)
    identifier = stable_urn(urn_kind, document)
    with_id = {**document, id_field: identifier}
    finalized = {**with_id, "content_digest": semantic_hash(with_id)}
    validate_contract(contract, finalized)
    return finalized


def verify_finalized_document(
    value: dict[str, Any],
    *,
    contract: str,
    id_field: str,
    urn_kind: str,
) -> None:
    expected = finalize_document(value, contract=contract, id_field=id_field, urn_kind=urn_kind)
    if value != expected:
        raise ValueError(f"{contract} deterministic ID or content digest mismatch")
