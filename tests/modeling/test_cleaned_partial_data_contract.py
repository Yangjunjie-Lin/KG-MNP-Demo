"""CleanedPartialData JSON Schema behavior."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from kg_mnp_demo.modeling.registry import validate_contract


ROOT = Path(__file__).resolve().parents[2]


def _minimal() -> dict[str, object]:
    return {
        "contract_version": "1.0",
        "document_id": "document-001",
        "dataset_id": "dataset-001",
        "data": {},
        "sources": [],
    }


def test_all_synthetic_cleaned_inputs_satisfy_the_generic_contract():
    paths = sorted((ROOT / "examples" / "modeling" / "inputs").glob("*.json"))
    assert paths
    for path in paths:
        validate_contract(
            "cleaned-partial-data",
            json.loads(path.read_text(encoding="utf-8")),
        )


@pytest.mark.parametrize("data", [{"anything": 1}, [1, None, {"x": False}]])
def test_data_accepts_arbitrary_json_objects_and_arrays(data: object):
    payload = _minimal()
    payload["data"] = data

    validate_contract("cleaned-partial-data", payload)


def test_explicit_null_has_a_distinct_null_presence_marker():
    payload = _minimal()
    payload["data"] = {"value": None}
    payload["field_metadata"] = [
        {
            "path": "/value",
            "source_refs": [],
            "presence": "NULL",
            "confidence": {"level": "UNKNOWN", "basis": "NOT_OBSERVED"},
        }
    ]

    validate_contract("cleaned-partial-data", payload)


def test_conflict_requires_all_alternatives_and_has_no_winner_field():
    payload = _minimal()
    payload["sources"] = [
        {
            "source_id": "source-a",
            "source_type": "DOCUMENT",
            "source_locator": "document:A",
            "source_version": "1",
        },
        {
            "source_id": "source-b",
            "source_type": "DOCUMENT",
            "source_locator": "document:B",
            "source_version": "1",
        },
    ]
    payload["declared_conflicts"] = [
        {
            "conflict_id": "conflict-1",
            "path": "/status",
            "alternatives": [
                {"value": "ACTIVE", "source_refs": ["source-a"]},
                {"value": "SUSPENDED", "source_refs": ["source-b"]},
            ],
        }
    ]
    validate_contract("cleaned-partial-data", payload)

    invalid = copy.deepcopy(payload)
    invalid["declared_conflicts"][0]["winner"] = "ACTIVE"
    with pytest.raises(ValidationError):
        validate_contract("cleaned-partial-data", invalid)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(contract_version="2.0"),
        lambda value: value.pop("document_id"),
        lambda value: value.update(unexpected=True),
        lambda value: value.update(data="not-an-object-or-array"),
        lambda value: value.update(
            field_metadata=[
                {"path": "/x", "source_refs": [], "presence": "MISSING"}
            ]
        ),
    ],
)
def test_contract_rejects_wrong_version_missing_fields_and_forbidden_shapes(mutate):
    payload = _minimal()
    mutate(payload)

    with pytest.raises(ValidationError):
        validate_contract("cleaned-partial-data", payload)
