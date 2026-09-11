"""Deterministic Prompt 4 modeling-run state bound to finite limits."""

from __future__ import annotations

import copy
from typing import Any

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn
from zhigou_toolchain.contracts.registry import validate_contract

from .errors import StaleModelingArtifactError
from .limits import ModelingLimits


def _run_identity(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_lock_id": value["project_lock_id"],
        "modeling_input_bundle_id": value["modeling_input_bundle_id"],
        "limits": value["limits"],
    }


def build_modeling_run(
    *,
    project_lock_id: str,
    modeling_input_bundle_id: str,
    limits: ModelingLimits | None = None,
    proposal_id: str | None = None,
    review_queue_id: str | None = None,
    package_id: str | None = None,
    status: str = "INPUT_READY",
) -> dict[str, Any]:
    """Build one state revision while keeping the semantic run ID stable."""

    core = {
        "manifest_kind": "KG_MNP_ONTOLOGY_MODELING_RUN",
        "schema_version": "1.0.0",
        "project_lock_id": project_lock_id,
        "modeling_input_bundle_id": modeling_input_bundle_id,
        "proposal_id": proposal_id,
        "review_queue_id": review_queue_id,
        "package_id": package_id,
        "limits": (limits or ModelingLimits()).to_dict(),
        "status": status,
    }
    run_id = stable_urn("ontology-modeling-run", _run_identity(core))
    document = {
        **core,
        "modeling_run_id": run_id,
        "content_digest": semantic_hash({**core, "modeling_run_id": run_id}),
    }
    verify_modeling_run(document)
    return document


def advance_modeling_run(
    value: dict[str, Any],
    *,
    status: str,
    proposal_id: str | None = None,
    review_queue_id: str | None = None,
    package_id: str | None = None,
) -> dict[str, Any]:
    verify_modeling_run(value)
    updated = copy.deepcopy(value)
    updated["status"] = status
    if proposal_id is not None:
        updated["proposal_id"] = proposal_id
    if review_queue_id is not None:
        updated["review_queue_id"] = review_queue_id
    if package_id is not None:
        updated["package_id"] = package_id
    updated["content_digest"] = semantic_hash(
        {key: item for key, item in updated.items() if key != "content_digest"}
    )
    verify_modeling_run(updated)
    return updated


def verify_modeling_run(value: dict[str, Any]) -> None:
    validate_contract("ontology-modeling-run", value)
    expected_id = stable_urn("ontology-modeling-run", _run_identity(value))
    expected_digest = semantic_hash(
        {key: item for key, item in value.items() if key != "content_digest"}
    )
    if value["modeling_run_id"] != expected_id or value["content_digest"] != expected_digest:
        raise StaleModelingArtifactError("modeling run identity or digest mismatch")
    status = value["status"]
    if status in {"PROPOSED", "PREVALIDATED", "UNDER_REVIEW", "READY_FOR_COMPILATION"} and value["proposal_id"] is None:
        raise StaleModelingArtifactError("modeling run status requires a proposal")
    if status in {"UNDER_REVIEW", "READY_FOR_COMPILATION"} and value["review_queue_id"] is None:
        raise StaleModelingArtifactError("modeling run status requires a review queue")
    if status == "READY_FOR_COMPILATION" and value["package_id"] is None:
        raise StaleModelingArtifactError("compiler-ready modeling run requires a package")
