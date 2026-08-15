from __future__ import annotations

import pytest

from kg_mnp_demo.amendment.contracts import (
    AmendmentContractError,
    load_amendment_schema,
    strict_json_bytes,
)


def test_phase05_schemas_are_closed_and_identified() -> None:
    for name in (
        "amendment-intake-manifest",
        "verified-amendment-intake",
        "republication-result",
        "application-phase05-attestation",
    ):
        schema = load_amendment_schema(name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False


def test_duplicate_keys_are_rejected_case_insensitively() -> None:
    with pytest.raises(AmendmentContractError):
        strict_json_bytes(b'{"a": 1, "A": 2}')


def test_non_finite_numbers_are_rejected() -> None:
    with pytest.raises(AmendmentContractError):
        strict_json_bytes(b'{"a": NaN}')
