from __future__ import annotations

import math

import pytest

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash


def test_canonical_json_is_sorted_compact_utf8_and_repeatable() -> None:
    value = {"中文": "保留", "b": [2, 1], "a": {"z": True}}
    expected = '{"a":{"z":true},"b":[2,1],"中文":"保留"}'.encode()
    assert canonical_json_bytes(value) == expected
    assert canonical_json_bytes(value) == canonical_json_bytes(value)
    assert semantic_hash(value) == semantic_hash(value)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_canonical_json_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(ValueError):
        canonical_json_bytes({"value": value})

