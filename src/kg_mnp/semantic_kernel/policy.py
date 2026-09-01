"""Load and verify the immutable packaged semantic compiler policy."""

from __future__ import annotations

import copy
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.registry import validate_contract

from .limits import SemanticLimits


def _read_policy(path: Path | str | None) -> dict[str, Any]:
    if path is None:
        raw = resources.files("kg_mnp.semantic_kernel").joinpath(
            "resources/toolchain-compiler-policy-1.0.0.yaml"
        ).read_bytes()
    else:
        source = Path(path)
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 1_048_576:
            raise ValueError("unsafe compiler policy resource")
        raw = source.read_bytes()
    value = yaml.safe_load(raw)
    if not isinstance(value, dict):
        raise TypeError("compiler policy root must be an object")
    return value


def load_compiler_policy(path: Path | str | None = None) -> dict[str, Any]:
    policy = _read_policy(path)
    preimage = copy.deepcopy(policy)
    actual_id = preimage.pop("policy_id", None)
    actual_digest = preimage.pop("content_digest", None)
    expected_digest = semantic_hash(preimage)
    expected_id = stable_urn("semantic-compiler-policy", {"content_digest": expected_digest})
    if actual_digest != expected_digest or actual_id != expected_id:
        raise ValueError("semantic compiler policy identity mismatch")
    SemanticLimits(**policy["resource_limits"])
    validate_contract("semantic-compiler-policy", policy)
    return copy.deepcopy(policy)


def policy_resource_bytes() -> bytes:
    return resources.files("kg_mnp.semantic_kernel").joinpath(
        "resources/toolchain-compiler-policy-1.0.0.yaml"
    ).read_bytes()
