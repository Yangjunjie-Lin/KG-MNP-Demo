from __future__ import annotations

import json

import pytest

from kg_mnp_demo.workbench.contracts import (
    WORKBENCH_SCHEMAS,
    load_workbench_schema,
    strict_json_bytes,
)


def test_all_workbench_contracts_are_strict_draft_2020_12() -> None:
    identifiers = set()
    for name in WORKBENCH_SCHEMAS:
        schema = load_workbench_schema(name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False
        assert schema["$id"].startswith(
            "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/workbench/"
        )
        identifiers.add(schema["$id"])
    assert len(identifiers) == len(WORKBENCH_SCHEMAS)


def test_strict_json_rejects_duplicate_keys_and_non_finite_numbers() -> None:
    with pytest.raises(ValueError, match="duplicate JSON key"):
        strict_json_bytes(b'{"status":"PASS","STATUS":"FAILED"}')
    with pytest.raises(ValueError, match="non-finite"):
        strict_json_bytes(b'{"value":NaN}')
    assert strict_json_bytes(json.dumps({"status": "PASS"}).encode()) == {
        "status": "PASS"
    }
