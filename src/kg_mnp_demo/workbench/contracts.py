"""Strict JSON Schema contracts for the Phase 02 presentation layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from kg_mnp_demo.modeling.dependencies import ROOT


WORKBENCH_SCHEMAS = {
    "runtime-policy": (
        "workbench_runtime_policy.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/workbench/runtime-policy/1.0",
    ),
    "manifest": (
        "workbench_manifest.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/workbench/manifest/1.0",
    ),
    "attestation": (
        "workbench_attestation.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/workbench/attestation/1.0",
    ),
    "entity-view-model": (
        "entity_view_model.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/workbench/entity-view-model/1.0",
    ),
    "fact-trace-view-model": (
        "fact_trace_view_model.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/workbench/fact-trace-view-model/1.0",
    ),
}


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    folded: set[str] = set()
    for key, value in pairs:
        marker = key.casefold()
        if marker in folded:
            raise ValueError("duplicate JSON key")
        folded.add(marker)
        result[key] = value
    return result


def strict_json_bytes(raw: bytes) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_json_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("non-finite JSON number")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid strict JSON") from exc


def strict_json_file(path: Path) -> dict[str, Any]:
    value = strict_json_bytes(Path(path).read_bytes())
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def load_workbench_schema(name: str, root: Path = ROOT) -> dict[str, Any]:
    if name not in WORKBENCH_SCHEMAS:
        raise ValueError(f"unknown workbench contract: {name}")
    filename, identifier = WORKBENCH_SCHEMAS[name]
    document = strict_json_file(Path(root) / "schemas" / "workbench" / filename)
    if (
        document.get("$schema")
        != "https://json-schema.org/draft/2020-12/schema"
        or document.get("$id") != identifier
        or document.get("additionalProperties") is not False
    ):
        raise ValueError(f"invalid workbench schema identity: {name}")
    Draft202012Validator.check_schema(document)
    return document


def validate_workbench_contract(
    name: str,
    payload: Any,
    root: Path = ROOT,
) -> None:
    errors = sorted(
        Draft202012Validator(
            load_workbench_schema(name, root),
            format_checker=FormatChecker(),
        ).iter_errors(payload),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise ValueError(f"{name}: {errors[0].message}")
