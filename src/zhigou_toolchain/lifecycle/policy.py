"""Load and verify bundled lifecycle policies without network access."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from zhigou_toolchain.contracts.canonical import semantic_hash, stable_urn

from .errors import LifecycleError

RESOURCE_DIR = Path(__file__).with_name("resources")


def load_policy(name: str, *, resource_dir: Path | str = RESOURCE_DIR) -> dict[str, Any]:
    safe = Path(name).name
    if safe != name or not safe.endswith(".yaml"):
        raise LifecycleError("LIFECYCLE_CONTRACT_INVALID", "unsafe lifecycle policy name")
    path = Path(resource_dir) / safe
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise LifecycleError("LIFECYCLE_ARTIFACT_MISSING", f"policy unavailable: {name}") from exc
    if not isinstance(value, dict):
        raise LifecycleError("LIFECYCLE_CONTRACT_INVALID", "policy must be an object")
    expected_digest = semantic_hash({k: v for k, v in value.items() if k not in {"policy_id", "content_digest"}})
    if value.get("content_digest") != expected_digest:
        raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", f"policy digest mismatch: {name}")
    policy_kind = {
        "registry-policy-1.0.0.yaml": "ontology-registry-policy",
        "semantic-diff-policy-1.0.0.yaml": "semantic-diff-policy",
        "regression-policy-1.0.0.yaml": "regression-policy",
        "release-policy-1.0.0.yaml": "release-policy",
        "activation-policy-1.0.0.yaml": "activation-policy",
    }.get(safe)
    if policy_kind is None:
        raise LifecycleError("LIFECYCLE_CONTRACT_INVALID", "unknown lifecycle policy")
    expected_id = stable_urn(policy_kind, {"content_digest": expected_digest})
    if value.get("policy_id") != expected_id:
        raise LifecycleError("LIFECYCLE_ARTIFACT_TAMPERED", f"policy identity mismatch: {name}")
    return value


__all__ = ["RESOURCE_DIR", "load_policy"]
