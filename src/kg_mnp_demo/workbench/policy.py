"""Frozen local-only workbench runtime policy."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.modeling.dependencies import ROOT

from .contracts import validate_workbench_contract


POLICY_PATH = ROOT / "config" / "workbench" / "workbench-runtime-1.0.0.yaml"
WORKBENCH_VERSION = "1.0.0"
ALLOWED_PHASE01_ROUTES = (
    "/api/v1/health",
    "/api/v1/ontology/classes",
    "/api/v1/ontology/properties",
    "/api/v1/ontology/term",
    "/api/v1/entity",
    "/api/v1/entity/provenance",
    "/api/v1/fact",
    "/api/v1/fact/provenance",
    "/api/v1/review-trace",
    "/api/v1/source-trace",
    "/api/v1/evidence-trace",
    "/api/v1/trace",
)


class WorkbenchPolicyError(ValueError):
    pass


class _Loader(yaml.SafeLoader):
    pass


def _mapping(
    loader: _Loader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise WorkbenchPolicyError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_workbench_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)
    except (OSError, UnicodeError, yaml.YAMLError, WorkbenchPolicyError) as exc:
        raise WorkbenchPolicyError("cannot read workbench runtime policy") from exc
    if not isinstance(value, dict):
        raise WorkbenchPolicyError("workbench policy root must be an object")
    validate_workbench_contract("runtime-policy", value, path.resolve().parents[2])
    if (
        value.get("runtime_id") != "kg-mnp-evidence-workbench"
        or value.get("workbench_version") != WORKBENCH_VERSION
        or value.get("network", {}).get("bind_host") != "127.0.0.1"
        or tuple(value.get("relay", {}).get("allowed_routes", ()))
        != ALLOWED_PHASE01_ROUTES
    ):
        raise WorkbenchPolicyError("workbench policy identity mismatch")
    return value


def workbench_policy_hash(policy: dict[str, Any] | None = None) -> str:
    payload = policy or load_workbench_policy()
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
