"""Closed Draft 2020-12 governance contracts and strict JSON loading."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from kg_mnp_demo.modeling.dependencies import ROOT

SCHEMAS = {
    "resolution-proposal": (
        "resolution_proposal.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/governance/resolution-proposal/1.0",
    ),
    "resolution-review-decision": (
        "resolution_review_decision.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/governance/resolution-review-decision/1.0",
    ),
    "governance-event": (
        "governance_event.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/governance/governance-event/1.0",
    ),
    "approved-amendment-request": (
        "approved_amendment_request.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/governance/approved-amendment-request/1.0",
    ),
    "governance-workspace": (
        "governance_workspace.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/governance/governance-workspace/1.0",
    ),
    "application-phase04-attestation": (
        "application_phase04_attestation.schema.json",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/governance/application-phase04-attestation/1.0",
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
        raise TypeError("JSON root must be an object")
    return value


@lru_cache(maxsize=len(SCHEMAS))
def _schema(name: str, root: Path = ROOT) -> dict[str, Any]:
    if name not in SCHEMAS:
        raise ValueError(f"unknown governance contract: {name}")
    filename, identifier = SCHEMAS[name]
    value = strict_json_file(Path(root) / "schemas" / "governance" / filename)
    if (
        value.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or value.get("$id") != identifier
        or value.get("additionalProperties") is not False
    ):
        raise ValueError(f"invalid governance schema identity: {name}")
    Draft202012Validator.check_schema(value)
    return value


def load_governance_schema(name: str, root: Path = ROOT) -> dict[str, Any]:
    return deepcopy(_schema(name, root))


def validate_governance_contract(name: str, value: Any, root: Path = ROOT) -> None:
    errors = sorted(
        Draft202012Validator(
            load_governance_schema(name, root),
            format_checker=FormatChecker(),
        ).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        location = "/".join(str(part) for part in errors[0].absolute_path)
        raise ValueError(f"{name} at {location or '<root>'}: {errors[0].message}")


def governance_contract_hash(root: Path = ROOT) -> str:
    from kg_mnp_demo.modeling.canonical_json import semantic_hash

    return semantic_hash(
        {name: load_governance_schema(name, root) for name in sorted(SCHEMAS)}
    )
