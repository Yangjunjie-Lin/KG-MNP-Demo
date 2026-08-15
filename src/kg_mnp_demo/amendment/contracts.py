"""Strict Draft 2020-12 contracts for Phase 05 documents."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from kg_mnp_demo.modeling.canonical_json import semantic_hash
from kg_mnp_demo.modeling.dependencies import ROOT

from .errors import AmendmentError

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
SCHEMAS: dict[str, tuple[str, str]] = {
    "amendment-intake-manifest": (
        "amendment_intake_manifest.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/amendment/amendment-intake-manifest/1.0",
    ),
    "verified-amendment-intake": (
        "verified_amendment_intake.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/amendment/verified-amendment-intake/1.0",
    ),
    "republication-result": (
        "republication_result.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/amendment/republication-result/1.0",
    ),
    "application-phase05-attestation": (
        "application_phase05_attestation.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/amendment/application-phase05-attestation/1.0",
    ),
}


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    folded: set[str] = set()
    for key, value in pairs:
        marker = key.casefold()
        if marker in folded:
            raise AmendmentError("INVALID_CONTRACT", f"duplicate JSON key: {key}")
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
    except (UnicodeError, json.JSONDecodeError, ValueError, AmendmentError) as exc:
        raise AmendmentContractError("invalid strict JSON") from exc


def strict_json_file(path: Path) -> dict[str, Any]:
    value = strict_json_bytes(Path(path).read_bytes())
    if not isinstance(value, dict):
        raise AmendmentContractError("JSON root must be an object")
    return value


class AmendmentContractError(ValueError):
    """Contract parsing/validation failed."""


@lru_cache(maxsize=len(SCHEMAS))
def load_amendment_schema(name: str, root: Path = ROOT) -> dict[str, Any]:
    if name not in SCHEMAS:
        raise AmendmentContractError(f"unknown amendment contract: {name}")
    filename, identifier = SCHEMAS[name]
    value = strict_json_file(Path(root) / "schemas" / "amendment" / filename)
    if (
        value.get("$schema") != DRAFT_2020_12
        or value.get("$id") != identifier
        or value.get("additionalProperties") is not False
    ):
        raise AmendmentContractError(f"invalid amendment schema identity: {name}")
    Draft202012Validator.check_schema(value)
    return value


def validate_amendment_contract(name: str, value: Any, root: Path = ROOT) -> None:
    try:
        errors = sorted(
            Draft202012Validator(
                load_amendment_schema(name, root), format_checker=FormatChecker()
            ).iter_errors(value),
            key=lambda error: list(error.absolute_path),
        )
    except Exception as exc:
        raise AmendmentContractError(str(exc)) from exc
    if errors:
        location = "/".join(str(part) for part in errors[0].absolute_path)
        raise AmendmentContractError(
            f"{name} at {location or '<root>'}: {errors[0].message}"
        )


def amendment_contract_hash(root: Path = ROOT) -> str:
    return semantic_hash(
        {name: load_amendment_schema(name, root) for name in sorted(SCHEMAS)}
    )
