from __future__ import annotations

import json
import math
from importlib import resources
from pathlib import Path

import pytest

from kg_mnp.contracts import (
    ContractCatalog,
    canonical_json_bytes,
    contract_names,
    file_sha256,
    get_contract_schema,
    semantic_hash,
    stable_urn,
    validate_contract,
    verify_catalog_lock,
)
from kg_mnp.contracts.catalog import DRAFT_2020_12, regenerate_catalog_files

PROMPT05_CONTRACT_COUNT = 115


def test_catalog_is_the_unique_closed_public_authority() -> None:
    catalog = ContractCatalog.load()
    assert len(catalog.specs) >= PROMPT05_CONTRACT_COUNT
    assert contract_names() == tuple(spec.name for spec in catalog.specs)
    for attribute in ("name", "schema_id", "resource_path"):
        values = [getattr(spec, attribute) for spec in catalog.specs]
        assert len(values) == len(set(values))
    pairs = [(spec.name, spec.version) for spec in catalog.specs]
    assert len(pairs) == len(set(pairs))


def test_catalog_self_validates_and_all_schemas_are_draft_2020_12() -> None:
    catalog = ContractCatalog.load()
    validate_contract("contract-catalog-v1-3", catalog.document)
    for spec in catalog.specs:
        schema = get_contract_schema(spec.name)
        assert schema["$id"] == spec.schema_id
        assert schema["$schema"] == DRAFT_2020_12


def test_catalog_lock_and_regeneration_are_deterministic_and_current() -> None:
    before_catalog = resources.files("kg_mnp.contracts").joinpath("catalog.json").read_bytes()
    before_lock = resources.files("kg_mnp.contracts").joinpath("catalog.lock.json").read_bytes()
    assert regenerate_catalog_files(check=True)
    assert verify_catalog_lock()["manifest_kind"] == "KG_MNP_CONTRACT_CATALOG_LOCK"
    assert resources.files("kg_mnp.contracts").joinpath("catalog.json").read_bytes() == before_catalog
    assert resources.files("kg_mnp.contracts").joinpath("catalog.lock.json").read_bytes() == before_lock
    assert b"generated_at" not in before_lock


def test_packaged_resources_are_accessible_without_repository_path_arithmetic() -> None:
    package = resources.files("kg_mnp.contracts")
    assert package.joinpath("catalog.json").is_file()
    for spec in ContractCatalog.load().specs:
        assert package.joinpath(spec.resource_path).is_file()


def test_canonical_json_hashes_and_identifiers_are_stable(tmp_path: Path) -> None:
    left = {"z": ["é", 1], "a": {"b": True}}
    right = {"a": {"b": True}, "z": ["é", 1]}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert semantic_hash(left) == semantic_hash(right)
    assert stable_urn("artifact", left) == stable_urn("artifact", right)
    path = tmp_path / "content.bin"
    path.write_bytes(b"contract-bytes")
    assert file_sha256(path) == "e9d3a6ba74b7588a4633ec346e84daa93696004dab142878217e295aec97d926"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_canonical_json_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(ValueError):
        canonical_json_bytes({"value": value})


def test_stable_urn_rejects_uncontrolled_kind() -> None:
    with pytest.raises(ValueError):
        stable_urn("Bad/Kind", {})


def test_no_public_schema_declares_secret_fields_or_remote_file_refs() -> None:
    forbidden = {"secret", "password", "token", "api_key", "api-key"}

    def walk(value: object, properties: list[str]) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("properties"), dict):
                properties.extend(value["properties"])
            for item in value.values():
                walk(item, properties)
        elif isinstance(value, list):
            for item in value:
                walk(item, properties)

    for name in contract_names():
        schema = get_contract_schema(name)
        serialized = json.dumps(schema, sort_keys=True)
        assert "file://" not in serialized
        properties: list[str] = []

        walk(schema, properties)
        assert forbidden.isdisjoint(key.casefold() for key in properties)
