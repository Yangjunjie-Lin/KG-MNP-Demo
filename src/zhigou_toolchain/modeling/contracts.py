"""Compatibility metadata filtered from the single public Contract Catalog."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from zhigou_toolchain.contracts.catalog import (
    DRAFT_2020_12,
    ContractCatalog,
    ContractSpec,
)
from zhigou_toolchain.contracts.catalog import (
    normalize_contract_name as _normalize,
)
from zhigou_toolchain.contracts.errors import (
    ContractRegistryError,
    UnknownContractError,
)

MODELING_SCHEMA_BASE = (
    "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/"
)
CONTRACT_SPECS = ContractCatalog.load().filtered(scope="modeling")
CONTRACT_NAMES = tuple(spec.name for spec in CONTRACT_SPECS)
CONTRACT_BY_NAME = {spec.name: spec for spec in CONTRACT_SPECS}
CONTRACT_BY_FILENAME = {spec.filename: spec for spec in CONTRACT_SPECS}
CONTRACT_BY_ID = {spec.schema_id: spec for spec in CONTRACT_SPECS}


def normalize_contract_name(contract_name: str) -> str:
    return _normalize(contract_name, CONTRACT_SPECS)


def load_contract_registry(*args: Any, **kwargs: Any):
    from .registry import load_contract_registry as load

    return load(*args, **kwargs)


def get_contract_schema(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from .registry import get_contract_schema as get

    return get(*args, **kwargs)


def validate_contract(
    contract_name: str,
    payload: Mapping[str, Any] | list[Any],
    **kwargs: Any,
) -> None:
    from .registry import validate_contract as validate

    validate(contract_name, payload, **kwargs)


__all__ = [
    "CONTRACT_BY_FILENAME",
    "CONTRACT_BY_ID",
    "CONTRACT_BY_NAME",
    "CONTRACT_NAMES",
    "CONTRACT_SPECS",
    "DRAFT_2020_12",
    "MODELING_SCHEMA_BASE",
    "ContractRegistryError",
    "ContractSpec",
    "UnknownContractError",
    "get_contract_schema",
    "load_contract_registry",
    "normalize_contract_name",
    "validate_contract",
]
