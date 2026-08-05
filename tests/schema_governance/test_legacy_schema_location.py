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


def test_stage_04_modeling_schemas_have_not_been_created() -> None:
    modeling_schema_names = (
        "cleaned_partial_data.schema.json",
        "modeling_proposal.schema.json",
        "review_decision_log.schema.json",
        "confirmed_modeling_package.schema.json",
    )

    for name in modeling_schema_names:
        assert not (ROOT / "schemas" / "modeling" / name).exists()
