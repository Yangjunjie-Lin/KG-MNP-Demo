"""Offline registry coverage for the eight Stage 04 contracts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from kg_mnp_demo.modeling.contracts import (
    CONTRACT_SPECS,
    DRAFT_2020_12,
    ContractRegistryError,
    UnknownContractError,
)
from kg_mnp_demo.modeling.registry import (
    contract_names,
    get_contract_schema,
    load_contract_registry,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "modeling"


def _contract_copy(tmp_path: Path) -> Path:
    destination = tmp_path / "modeling"
    shutil.copytree(SCHEMA_DIR, destination)
    return destination


def test_registry_loads_exact_closed_catalog_with_unique_project_ids():
    registry = load_contract_registry()

    assert contract_names() == tuple(spec.name for spec in CONTRACT_SPECS)
    assert len(registry) == len(CONTRACT_SPECS) == 8
    schemas = [get_contract_schema(spec.name) for spec in CONTRACT_SPECS]
    assert {schema["$id"] for schema in schemas} == {
        spec.schema_id for spec in CONTRACT_SPECS
    }
    assert all(schema["$schema"] == DRAFT_2020_12 for schema in schemas)
    assert all(
        schema["$id"].startswith(
            "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/"
        )
        for schema in schemas
    )


def test_get_schema_accepts_local_aliases_and_returns_an_isolated_copy():
    first = get_contract_schema("cleaned_partial_data")
    second = get_contract_schema("cleaned_partial_data.schema.json")
    first["title"] = "mutated only in caller"

    assert second["title"] == "CleanedPartialData Contract 1.0"


def test_registry_rejects_unknown_contract_name():
    with pytest.raises(UnknownContractError):
        get_contract_schema("not-a-contract")


def test_registry_rejects_missing_schema_file(tmp_path: Path):
    copied = _contract_copy(tmp_path)
    (copied / "mapping_rules.schema.json").unlink()

    with pytest.raises(ContractRegistryError, match="missing"):
        load_contract_registry(copied)


def test_registry_rejects_duplicate_schema_id(tmp_path: Path):
    copied = _contract_copy(tmp_path)
    duplicate = json.loads((copied / "common.schema.json").read_text(encoding="utf-8"))
    (copied / "duplicate.schema.json").write_text(
        json.dumps(duplicate), encoding="utf-8"
    )

    with pytest.raises(ContractRegistryError, match="duplicate schema \\$id"):
        load_contract_registry(copied)


def test_registry_fails_closed_for_unknown_ref_without_network(tmp_path: Path):
    copied = _contract_copy(tmp_path)
    path = copied / "cleaned_partial_data.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    schema["properties"]["contract_version"]["$ref"] = (
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/missing/1.0"
    )
    path.write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(ContractRegistryError, match="unresolvable local \\$ref"):
        load_contract_registry(copied)


def test_registry_reports_cross_contract_reference_cycles(tmp_path: Path):
    copied = _contract_copy(tmp_path)
    common_path = copied / "common.schema.json"
    common = json.loads(common_path.read_text(encoding="utf-8"))
    common["$defs"]["Cycle"] = {
        "$ref": (
            "https://yangjunjie-lin.github.io/KG-MNP-Demo/"
            "schemas/modeling/cleaned-partial-data/1.0"
        )
    }
    common_path.write_text(json.dumps(common), encoding="utf-8")

    with pytest.raises(ContractRegistryError, match="cyclic cross-contract"):
        load_contract_registry(copied)
