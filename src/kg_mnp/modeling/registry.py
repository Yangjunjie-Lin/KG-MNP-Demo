"""Thin Modeling compatibility layer over :mod:`kg_mnp.contracts`."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from kg_mnp.contracts.registry import build_contract_registry

from .contracts import CONTRACT_SPECS, ContractRegistryError, normalize_contract_name

DEFAULT_SCHEMA_DIRECTORY: Path | None = None


def _bundle(schema_directory: Path | str | None):
    if schema_directory is None:
        return build_contract_registry(specs=CONTRACT_SPECS)
    directory = Path(schema_directory)
    bundle = build_contract_registry(
        schema_directory=directory,
        specs=CONTRACT_SPECS,
        verify_catalog=False,
    )
    known_ids = {
        bundle.schemas_by_name[spec.name]["$id"]: spec.filename
        for spec in CONTRACT_SPECS
    }
    expected = {spec.filename for spec in CONTRACT_SPECS}
    for path in sorted(directory.glob("*.schema.json")):
        if path.name in expected:
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ContractRegistryError(f"cannot load schema {path.name}: {exc}") from exc
        identifier = value.get("$id") if isinstance(value, dict) else None
        if identifier in known_ids:
            raise ContractRegistryError(
                f"duplicate schema $id {identifier!r}: {known_ids[identifier]}, {path.name}"
            )
    return bundle


def load_contract_registry(schema_directory: Path | str | None = None):
    return _bundle(schema_directory).registry


def get_contract_schema(
    contract_name: str,
    *,
    schema_directory: Path | str | None = None,
) -> dict[str, Any]:
    canonical = normalize_contract_name(contract_name)
    return _bundle(schema_directory).get_schema(canonical)


def validate_contract(
    contract_name: str,
    payload: Mapping[str, Any] | list[Any],
    *,
    schema_directory: Path | str | None = None,
) -> None:
    canonical = normalize_contract_name(contract_name)
    _bundle(schema_directory).validate(canonical, payload)


def contract_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in CONTRACT_SPECS)
