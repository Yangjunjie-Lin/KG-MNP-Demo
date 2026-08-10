"""Deterministic, RDF-faithful presentation models."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from kg_mnp_demo.application.contracts import validate_application_contract
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

from .contracts import validate_workbench_contract


FACT_TRACE_QUERY_ID = "provenance.fact"


def build_view_model(
    result: dict[str, Any],
    *,
    view_type: str,
) -> dict[str, Any]:
    """Remove only nondeterministic runtime metadata and preserve semantic data."""

    validate_application_contract("query-result", result)
    if result["result_count"] != len(result["results"]):
        raise ValueError("Phase 01 result count does not match its rows")
    provisional = {
        "contract_version": "1.0",
        "view_type": view_type,
        "query_id": result["query_id"],
        "publication_id": result["publication_id"],
        "publication_semantic_hash": result["publication_semantic_hash"],
        "repository_id": result["repository_id"],
        "parameters": copy.deepcopy(result["parameters"]),
        "variables": copy.deepcopy(result["variables"]),
        "rows": copy.deepcopy(result["results"]),
        "traceability": copy.deepcopy(result["traceability"]),
        "result_count": result["result_count"],
        "truncated": result["truncated"],
        "source_result_hash": result["result_semantic_hash"],
    }
    payload = {
        **provisional,
        "view_model_hash": hashlib.sha256(
            canonical_json_bytes(provisional)
        ).hexdigest(),
    }
    contract = (
        "fact-trace-view-model"
        if view_type == "FACT_TRACE"
        else "entity-view-model"
    )
    validate_workbench_contract(contract, payload)
    return payload


def assert_view_model_fidelity(
    result: dict[str, Any],
    view_model: dict[str, Any],
) -> None:
    if (
        view_model.get("source_result_hash") != result.get("result_semantic_hash")
        or view_model.get("rows") != result.get("results")
        or view_model.get("variables") != result.get("variables")
        or view_model.get("traceability") != result.get("traceability")
        or view_model.get("publication_id") != result.get("publication_id")
        or view_model.get("publication_semantic_hash")
        != result.get("publication_semantic_hash")
        or view_model.get("repository_id") != result.get("repository_id")
    ):
        raise ValueError("view model lost Phase 01 semantic fidelity")
