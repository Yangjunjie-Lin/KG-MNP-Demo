"""Closed JSON Schema contracts and strict local document loading."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from kg_mnp_demo.modeling.dependencies import ROOT


DIAGNOSTIC_SCHEMAS = {
    "diagnostic-policy": (
        "diagnostic_policy.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/diagnostics/diagnostic-policy/1.0",
    ),
    "diagnostic-issue": (
        "diagnostic_issue.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/diagnostics/diagnostic-issue/1.0",
    ),
    "diagnostic-package": (
        "diagnostic_package.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/diagnostics/diagnostic-package/1.0",
    ),
    "diagnostic-manifest": (
        "diagnostic_manifest.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/diagnostics/diagnostic-manifest/1.0",
    ),
    "diagnostic-attestation": (
        "diagnostic_attestation.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/diagnostics/diagnostic-attestation/1.0",
    ),
}


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    folded: set[str] = set()
    for key, value in pairs:
        marker = key.casefold()
        if marker in folded:
            raise ValueError(f"duplicate JSON key: {key}")
        folded.add(marker)
        result[key] = value
    return result


def strict_json_bytes(raw: bytes) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid strict JSON") from exc


def strict_json_file(path: Path) -> dict[str, Any]:
    value = strict_json_bytes(Path(path).read_bytes())
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


@lru_cache(maxsize=len(DIAGNOSTIC_SCHEMAS))
def _load_diagnostic_schema_cached(
    name: str,
    root: Path = ROOT,
) -> dict[str, Any]:
    if name not in DIAGNOSTIC_SCHEMAS:
        raise ValueError(f"unknown diagnostic contract: {name}")
    filename, identifier = DIAGNOSTIC_SCHEMAS[name]
    document = strict_json_file(
        Path(root) / "schemas" / "diagnostics" / filename
    )
    if (
        document.get("$schema")
        != "https://json-schema.org/draft/2020-12/schema"
        or document.get("$id") != identifier
        or document.get("additionalProperties") is not False
    ):
        raise ValueError(f"invalid diagnostic schema identity: {name}")
    Draft202012Validator.check_schema(document)
    return document


def load_diagnostic_schema(
    name: str,
    root: Path = ROOT,
) -> dict[str, Any]:
    return deepcopy(_load_diagnostic_schema_cached(name, root))


def validate_diagnostic_contract(
    name: str,
    payload: Any,
    root: Path = ROOT,
) -> None:
    errors = sorted(
        Draft202012Validator(
            load_diagnostic_schema(name, root),
            format_checker=FormatChecker(),
        ).iter_errors(payload),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        location = "/".join(str(value) for value in errors[0].absolute_path)
        raise ValueError(f"{name} at {location or '<root>'}: {errors[0].message}")
