"""Closed lifecycle artifact identity, validation and safe canonicalization."""
from __future__ import annotations

import copy
import re
from datetime import UTC, datetime
from typing import Any

from kg_mnp.contracts.canonical import canonical_json_bytes, semantic_hash, stable_urn
from kg_mnp.contracts.registry import get_contract_schema, validate_contract
from kg_mnp.semantic_kernel.security import assert_safe_json, scan_prohibited_text

from .errors import LifecycleError

_ID = re.compile(r"^urn:kg-mnp:[a-z0-9-]+:[0-9a-f]{64}$")
_TIME = {"registry-event", "release-review-action", "activation-review-decision", "activation-execution-receipt"}
_ORDERED = {"actions", "release_lineage", "illegal_cycles"}

def canonicalize(value: Any, field: str = "") -> Any:
    if isinstance(value, dict): return {k: canonicalize(v, k) for k, v in sorted(value.items())}
    if isinstance(value, list):
        items = [canonicalize(v) for v in value]
        return items if field in _ORDERED else sorted(items, key=canonical_json_bytes)
    return value

def contract_for(value: dict[str, Any]) -> str:
    target = value.get("manifest_kind")
    from kg_mnp.contracts.registry import load_contract_registry
    hits = []
    for spec in load_contract_registry().specs:
        if spec.scope != "lifecycle": continue
        schema = get_contract_schema(spec.name)
        if schema.get("properties", {}).get("manifest_kind", {}).get("const") == target: hits.append(spec.name)
    if len(hits) != 1: raise LifecycleError("LIFECYCLE_CONTRACT_INVALID", "unknown lifecycle artifact kind")
    return hits[0]

def identity_field(contract: str) -> str:
    schema = get_contract_schema(contract)
    return schema.get("x-identity-field", {"lifecycle-common":"artifact_id"}.get(contract, "content_digest"))

def _core(contract: str, value: dict[str, Any]) -> dict[str, Any]:
    ident = identity_field(contract); result = copy.deepcopy(value)
    result.pop(ident, None); result.pop("content_digest", None)
    for key in ("semantic_event_hash", "event_hash", "semantic_action_hash", "action_hash", "semantic_decision_hash", "head_hash", "pointer_hash"): result.pop(key, None)
    if contract in _TIME: result.pop("observed_at", None)
    if contract == "registry-event": result.pop("previous_event_hash", None); result.pop("previous_semantic_event_hash", None)
    if contract == "release-review-action": result.pop("previous_action_hash", None); result.pop("previous_semantic_action_hash", None)
    return result

def build(contract: str, **fields: Any) -> dict[str, Any]:
    schema = get_contract_schema(contract); value = {"manifest_kind": schema["properties"]["manifest_kind"]["const"], "schema_version":"1.0.0", **fields}
    value = canonicalize(value); digest = semantic_hash(_core(contract, value)); value["content_digest"] = digest
    ident = identity_field(contract)
    if contract == "ontology-registry-manifest": value[ident] = stable_urn("ontology-registry", {k:value[k] for k in ("registry_name","project_id","registry_scope","policy_digest")})
    elif contract == "registry-event": value[ident] = stable_urn(contract, {"semantic_event_hash": digest})
    else:
        # Release manifests have always been minted as urn:kg-mnp:release:...
        # by the release authority; the schema name is not its identity kind.
        kind = "release" if contract == "release-manifest" else contract
        value[ident] = stable_urn(kind, {"content_digest": digest})
    if contract == "registry-event": value["semantic_event_hash"] = digest; value["event_hash"] = semantic_hash(value)
    elif contract == "release-review-action": value["semantic_action_hash"] = digest; value["action_hash"] = semantic_hash(value)
    elif contract == "activation-review-decision": value["semantic_decision_hash"] = digest
    elif contract == "release-review-decision-log": value["semantic_decision_hash"] = semantic_hash(value.get("actions", []))
    elif contract == "registry-head": value["head_hash"] = digest
    elif contract == "environment-pointer": value["pointer_hash"] = digest
    validate(contract, value); return value

def validate(contract: str, value: dict[str, Any]) -> None:
    try:
        assert_safe_json(value)
        if scan_prohibited_text(canonical_json_bytes(value)): raise ValueError("unsafe path or secret content")
        validate_contract(contract, value)
        if canonicalize(value) != value: raise ValueError("nondeterministic collection ordering")
        if "observed_at" in value:
            dt = datetime.fromisoformat(value["observed_at"])
            if not value["observed_at"].endswith("Z") or dt.utcoffset() != UTC.utcoffset(dt): raise ValueError("observed_at must be UTC")
    except Exception as exc: raise LifecycleError("LIFECYCLE_CONTRACT_INVALID", str(exc)) from exc

def verify(value: dict[str, Any], *, contract: str | None = None, registry_id: str | None = None) -> dict[str, Any]:
    contract = contract or contract_for(value); validate(contract, value)
    if registry_id is not None and value.get("registry_id") != registry_id: raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", "cross-registry artifact")
    expected = build(contract, **{k:v for k,v in value.items() if k not in {identity_field(contract), "content_digest", "semantic_event_hash", "event_hash", "semantic_action_hash", "action_hash", "semantic_decision_hash", "head_hash", "pointer_hash"}})
    # Previous hashes are semantic links and are included by callers after construction.
    for key in (identity_field(contract), "content_digest"):
        if expected.get(key) != value.get(key): raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", "identity or digest mismatch")
    return value
