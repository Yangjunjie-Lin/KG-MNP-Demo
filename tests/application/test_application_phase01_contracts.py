from __future__ import annotations

import pytest

from kg_mnp_demo.application.contracts import (
    APPLICATION_SCHEMAS,
    load_application_schema,
    validate_application_contract,
)
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode


def test_all_phase01_contracts_are_offline_draft_202012_and_closed():
    def assert_closed_objects(value):
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value.get("additionalProperties") is False
            for child in value.values():
                assert_closed_objects(child)
        elif isinstance(value, list):
            for child in value:
                assert_closed_objects(child)

    for name in APPLICATION_SCHEMAS:
        schema = load_application_schema(name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith(
            "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/application/"
        )
        assert schema["additionalProperties"] is False
        assert_closed_objects(schema)


def test_error_contract_and_stable_phase01_codes():
    for code in (
        ErrorCode.INVALID_QUERY_ID,
        ErrorCode.INVALID_PARAMETER,
        ErrorCode.INVALID_IRI,
        ErrorCode.QUERY_TIMEOUT,
        ErrorCode.RESULT_LIMIT_EXCEEDED,
        ErrorCode.FOUNDATION_NOT_VERIFIED,
        ErrorCode.PUBLICATION_MISMATCH,
        ErrorCode.GRAPHDB_UNAVAILABLE,
        ErrorCode.READ_ONLY_POLICY_VIOLATION,
        ErrorCode.INTERNAL_ERROR,
    ):
        payload = ApplicationError(code).to_dict()
        validate_application_contract("error-response", payload)
        assert "traceback" not in str(payload).lower()


def test_query_request_rejects_unknown_properties():
    with pytest.raises(ValueError):
        validate_application_contract(
            "query-request",
            {
                "contract_version": "1.0",
                "query_id": "business.entity",
                "parameters": {"iri": "urn:kg-mnp:test"},
                "raw_sparql": "SELECT * WHERE {}",
            },
        )
