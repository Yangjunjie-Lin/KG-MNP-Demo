"""Names and identifiers for the Stage 04 modeling contracts.

This module deliberately contains no schema-loading side effects.  The local
registry is imported lazily by the convenience functions at the bottom so
importing contract metadata can never trigger I/O or remote resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
MODELING_SCHEMA_BASE = (
    "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/"
)


@dataclass(frozen=True)
class ContractSpec:
    """One versioned schema in the closed Stage 04 contract catalog."""

    name: str
    filename: str
    schema_id: str


CONTRACT_SPECS = (
    ContractSpec("common", "common.schema.json", f"{MODELING_SCHEMA_BASE}common/1.0"),
    ContractSpec(
        "cleaned-partial-data",
        "cleaned_partial_data.schema.json",
        f"{MODELING_SCHEMA_BASE}cleaned-partial-data/1.0",
    ),
    ContractSpec(
        "modeling-proposal",
        "modeling_proposal.schema.json",
        f"{MODELING_SCHEMA_BASE}modeling-proposal/1.0",
    ),
    ContractSpec(
        "review-decision-log",
        "review_decision_log.schema.json",
        f"{MODELING_SCHEMA_BASE}review-decision-log/1.0",
    ),
    ContractSpec(
        "confirmed-modeling-package",
        "confirmed_modeling_package.schema.json",
        f"{MODELING_SCHEMA_BASE}confirmed-modeling-package/1.0",
    ),
    ContractSpec(
        "ontology-baseline-manifest",
        "ontology_baseline_manifest.schema.json",
        f"{MODELING_SCHEMA_BASE}ontology-baseline-manifest/1.0",
    ),
    ContractSpec(
        "mapping-rules",
        "mapping_rules.schema.json",
        f"{MODELING_SCHEMA_BASE}mapping-rules/1.0",
    ),
    ContractSpec(
        "terminology-profile",
        "terminology_profile.schema.json",
        f"{MODELING_SCHEMA_BASE}terminology-profile/1.0",
    ),
    ContractSpec(
        "review-common",
        "review_common.schema.json",
        f"{MODELING_SCHEMA_BASE}review-common/1.0",
    ),
    ContractSpec(
        "review-action",
        "review_action.schema.json",
        f"{MODELING_SCHEMA_BASE}review-action/1.0",
    ),
    ContractSpec(
        "review-policy",
        "review_policy.schema.json",
        f"{MODELING_SCHEMA_BASE}review-policy/1.0",
    ),
)

CONTRACT_NAMES = tuple(spec.name for spec in CONTRACT_SPECS)
CONTRACT_BY_NAME = {spec.name: spec for spec in CONTRACT_SPECS}
CONTRACT_BY_FILENAME = {spec.filename: spec for spec in CONTRACT_SPECS}
CONTRACT_BY_ID = {spec.schema_id: spec for spec in CONTRACT_SPECS}


class ContractRegistryError(RuntimeError):
    """The local contract catalog is missing, inconsistent, or unresolvable."""


class UnknownContractError(KeyError):
    """A caller requested a name outside the closed contract catalog."""


def normalize_contract_name(contract_name: str) -> str:
    """Return the canonical kebab-case name, accepting safe local aliases."""

    if not isinstance(contract_name, str) or not contract_name.strip():
        raise UnknownContractError(contract_name)
    value = contract_name.strip()
    if value in CONTRACT_BY_ID:
        return CONTRACT_BY_ID[value].name
    filename = Path(value).name
    if filename in CONTRACT_BY_FILENAME:
        return CONTRACT_BY_FILENAME[filename].name
    value = value.removesuffix(".schema.json").replace("_", "-").lower()
    if value not in CONTRACT_BY_NAME:
        known = ", ".join(CONTRACT_NAMES)
        raise UnknownContractError(f"unknown contract {contract_name!r}; known: {known}")
    return value


def load_contract_registry(*args: Any, **kwargs: Any):
    """Compatibility import for :func:`modeling.registry.load_contract_registry`."""

    from .registry import load_contract_registry as load

    return load(*args, **kwargs)


def get_contract_schema(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Compatibility import for :func:`modeling.registry.get_contract_schema`."""

    from .registry import get_contract_schema as get

    return get(*args, **kwargs)


def validate_contract(
    contract_name: str,
    payload: Mapping[str, Any] | list[Any],
    **kwargs: Any,
) -> None:
    """Compatibility import for :func:`modeling.registry.validate_contract`."""

    from .registry import validate_contract as validate

    validate(contract_name, payload, **kwargs)
