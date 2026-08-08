from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from ..modeling.dependencies import ROOT

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
SPECS = {
    "webvowl-runtime-policy": (
        "webvowl_runtime_policy.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/webvowl/runtime-policy/1.0",
    ),
    "visualization-manifest": (
        "visualization_manifest.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/webvowl/visualization-manifest/1.0",
    ),
    "coverage-report": (
        "coverage_report.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/webvowl/coverage-report/1.0",
    ),
    "representation-loss": (
        "representation_loss.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/webvowl/representation-loss/1.0",
    ),
}


class WebVOWLContractError(ValueError):
    pass


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise WebVOWLContractError(f"duplicate JSON key: {k}")
        out[k] = v
    return out


def schema_path(name: str, root: Path = ROOT) -> Path:
    try:
        filename, _ = SPECS[name]
    except KeyError as exc:
        raise WebVOWLContractError(f"unknown WebVOWL contract: {name}") from exc
    return Path(root) / "schemas" / "webvowl" / filename


def load_webvowl_schema(name: str, root: Path = ROOT) -> dict[str, Any]:
    path = schema_path(name, root)
    try:
        schema = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
    except Exception as exc:
        raise WebVOWLContractError(f"cannot read schema {path}: {exc}") from exc
    if schema.get("$schema") != DRAFT_2020_12 or schema.get("$id") != SPECS[name][1]:
        raise WebVOWLContractError(f"invalid schema identifier: {path}")
    Draft202012Validator.check_schema(schema)
    return schema


def validate_webvowl_contract(
    name: str, payload: Mapping[str, Any], root: Path = ROOT
) -> None:
    schema = load_webvowl_schema(name, root)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            payload
        ),
        key=lambda e: list(e.absolute_path),
    )
    if errors:
        raise WebVOWLContractError(f"{name}: {errors[0].message}")
    if name == "visualization-manifest":
        from .identifiers import visualization_id, visualization_semantic_hash

        digest = visualization_semantic_hash(payload)
        if payload.get("visualization_semantic_hash") != digest or payload.get(
            "visualization_id"
        ) != visualization_id(digest):
            raise WebVOWLContractError("visualization manifest identity/hash mismatch")
