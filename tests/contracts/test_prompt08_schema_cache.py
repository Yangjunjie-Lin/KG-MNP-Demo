"""Content-keyed schema checking must not hide post-warmup tampering."""
from __future__ import annotations

import json

import pytest
from jsonschema import SchemaError

from kg_mnp.contracts.catalog import _check_schema_bytes


def test_schema_cache_keys_full_bytes_not_paths_or_prior_verdict():
    valid = json.dumps({"type": "string"}).encode()
    invalid = json.dumps({"type": "not-a-json-schema-type"}).encode()
    _check_schema_bytes.cache_clear()
    _check_schema_bytes(valid)
    _check_schema_bytes(valid)
    assert _check_schema_bytes.cache_info().hits == 1
    with pytest.raises(SchemaError):
        _check_schema_bytes(invalid)
    assert _check_schema_bytes.cache_info().currsize == 1


def test_schema_cache_rejects_non_json_even_after_warmup():
    _check_schema_bytes(b'{"type":"string"}')
    with pytest.raises(json.JSONDecodeError):
        _check_schema_bytes(b"{not-json")
