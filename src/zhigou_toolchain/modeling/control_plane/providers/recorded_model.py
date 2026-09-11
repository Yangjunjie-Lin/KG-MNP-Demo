"""Recorded external-model bytes and ModelInvocationRecord validation."""

from __future__ import annotations

import json
from typing import Any

from zhigou_toolchain.contracts.canonical import bytes_sha256, semantic_hash, stable_urn
from zhigou_toolchain.contracts.registry import validate_contract

from ..errors import ModelingProviderError
from ..limits import ModelingLimits
from ..security import assert_safe_json, validate_safe_relative_path


def verify_model_invocation_record(
    record: dict[str, Any],
    *,
    request_bytes: bytes | None = None,
    response_bytes: bytes | None = None,
) -> None:
    """Verify semantic identity and, when supplied, the exact recorded bytes."""

    validate_contract("model-invocation-record", record)
    assert_safe_json(record)
    semantic_core = {
        key: value
        for key, value in record.items()
        if key
        not in {
            "manifest_kind",
            "schema_version",
            "invocation_id",
            "semantic_digest",
        }
    }
    expected_digest = semantic_hash(semantic_core)
    expected_id = stable_urn("model-invocation", {"semantic_digest": expected_digest})
    if record["semantic_digest"] != expected_digest or record["invocation_id"] != expected_id:
        raise ModelingProviderError("ModelInvocationRecord semantic identity is tampered")
    if request_bytes is not None and bytes_sha256(request_bytes) != record["request_sha256"]:
        raise ModelingProviderError("recorded model request bytes are tampered")
    if response_bytes is not None and bytes_sha256(response_bytes) != record["response_sha256"]:
        raise ModelingProviderError("recorded model response bytes are tampered")


def import_recorded_model_output(
    raw_response: bytes,
    *,
    provider_name: str,
    model_id: str,
    model_revision: str,
    request_artifact_ref: str,
    request_bytes: bytes,
    response_artifact_ref: str,
    prompt_template_id: str,
    prompt_template_sha256: str,
    sampling_parameters: dict[str, int],
    declared_seed: int | None = None,
    determinism_class: str = "RECORDED_BYTES_ONLY",
    limits: ModelingLimits | None = None,
) -> tuple[tuple[dict, ...], dict[str, Any]]:
    effective = limits or ModelingLimits()
    if len(raw_response) > effective.max_model_response_bytes:
        raise ValueError("recorded model response exceeds byte limit")
    validate_safe_relative_path(request_artifact_ref)
    validate_safe_relative_path(response_artifact_ref)
    try:
        parsed = json.loads(raw_response.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"recorded model response is not UTF-8 JSON: {exc}") from exc
    if not isinstance(parsed, dict) or set(parsed) != {"candidate_drafts"} or not isinstance(parsed["candidate_drafts"], list):
        raise ValueError("recorded response must contain only candidate_drafts")
    assert_safe_json(parsed, provider_output=True, max_bytes=effective.max_model_response_bytes, max_depth=effective.max_model_json_depth)
    semantic_core = {
        "provider_type": "RECORDED_EXTERNAL_MODEL", "provider_name": provider_name,
        "model_id": model_id, "model_revision": model_revision,
        "request_artifact_ref": request_artifact_ref, "request_sha256": bytes_sha256(request_bytes),
        "response_artifact_ref": response_artifact_ref, "response_sha256": bytes_sha256(raw_response),
        "prompt_template_id": prompt_template_id, "prompt_template_sha256": prompt_template_sha256,
        "sampling_parameters": sampling_parameters, "declared_seed": declared_seed,
        "determinism_class": determinism_class, "finish_status": "RECORDED",
        "parse_status": "VALID", "issues": [],
    }
    semantic_digest = semantic_hash(semantic_core)
    record = {
        "manifest_kind": "KG_MNP_MODEL_INVOCATION_RECORD", "schema_version": "1.0.0",
        "invocation_id": stable_urn("model-invocation", {"semantic_digest": semantic_digest}),
        **semantic_core, "semantic_digest": semantic_digest,
    }
    verify_model_invocation_record(
        record,
        request_bytes=request_bytes,
        response_bytes=raw_response,
    )
    return tuple(parsed["candidate_drafts"]), record
