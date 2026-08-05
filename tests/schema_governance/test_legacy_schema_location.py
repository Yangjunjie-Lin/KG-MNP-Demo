"""Location and boundary checks for the legacy eligibility JSON Schema."""

from __future__ import annotations

from pathlib import Path

from kg_mnp_demo import input_adapter


ROOT = Path(__file__).resolve().parents[2]
LEGACY_SCHEMA = (
    ROOT
    / "examples"
    / "eligibility-use-case"
    / "schemas"
    / "mnp_case_input.schema.json"
)


def test_legacy_schema_is_owned_by_the_example_use_case() -> None:
    assert not (ROOT / "schemas" / "mnp_case_input.schema.json").exists()
    assert LEGACY_SCHEMA.is_file()
    assert input_adapter.LEGACY_ELIGIBILITY_SCHEMA_PATH == LEGACY_SCHEMA
    assert not hasattr(input_adapter, "SCHEMA_PATH")


def test_legacy_schema_loader_is_explicit_and_compatibility_alias_is_legacy() -> None:
    schema = input_adapter.load_legacy_eligibility_schema()

    assert input_adapter.load_schema() == schema
    assert schema["$id"].startswith(
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/legacy/"
    )
    assert "legacy eligibility" in (input_adapter.__doc__ or "").lower()
    assert "compatibility alias" in (input_adapter.load_schema.__doc__ or "").lower()


def test_legacy_adapter_does_not_load_central_modeling_contracts() -> None:
    assert "modeling" not in input_adapter.LEGACY_ELIGIBILITY_SCHEMA_PATH.parts
    assert "cleaned_partial_data" not in input_adapter.load_schema.__doc__.lower()
