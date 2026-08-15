from __future__ import annotations

import pytest

from kg_mnp_demo.amendment.diff import compute_cleaned_input_diff
from kg_mnp_demo.amendment.errors import AmendmentError, AmendmentErrorCode
from kg_mnp_demo.amendment.scope import validate_amendment_scope, validate_declared_diff


def _data(value: str = "old") -> dict:
    return {
        "contract_version": "1.0",
        "document_id": "d",
        "dataset_id": "dataset",
        "data": {"customer": {"msisdn": value, "name": "unchanged"}},
        "sources": [],
        "field_metadata": [
            {"path": "/data/customer/msisdn", "source_refs": [], "presence": "PRESENT"}
        ],
    }


def test_diff_includes_data_and_metadata() -> None:
    base = _data()
    revised = _data("new")
    revised["field_metadata"][0]["presence"] = "UNKNOWN"
    assert compute_cleaned_input_diff(base, revised) == [
        "/data/customer/msisdn",
        "/field_metadata/0/presence",
    ]


def test_undeclared_change_is_fail_closed() -> None:
    with pytest.raises(AmendmentError) as error:
        validate_declared_diff(_data(), _data("new"), ["/data/customer/name"])
    assert error.value.code == AmendmentErrorCode.UNDECLARED_INPUT_CHANGE


def test_scope_rejects_tbox_and_zero_diff_value() -> None:
    with pytest.raises(AmendmentError) as error:
        validate_amendment_scope(
            amendment_type="PROPOSE_CONSTRAINT_REVIEW",
            actual_changed_json_pointers=[],
            declared_changed_json_pointers=[],
        )
    assert (
        error.value.code == AmendmentErrorCode.TBOX_AMENDMENT_NOT_EXECUTABLE_IN_PHASE05
    )
    with pytest.raises(AmendmentError) as error:
        validate_amendment_scope(
            amendment_type="PROPOSE_VALUE_CANDIDATE",
            actual_changed_json_pointers=[],
            declared_changed_json_pointers=[],
        )
    assert error.value.code == AmendmentErrorCode.REENTRY_TARGET_UNRESOLVED


def test_review_reopen_requires_zero_diff() -> None:
    with pytest.raises(AmendmentError):
        validate_amendment_scope(
            amendment_type="REQUEST_REVIEW_REOPEN",
            actual_changed_json_pointers=["/data/customer/msisdn"],
            declared_changed_json_pointers=["/data/customer/msisdn"],
        )


def test_declared_but_out_of_target_scope_change_is_rejected() -> None:
    with pytest.raises(AmendmentError) as error:
        validate_amendment_scope(
            amendment_type="PROPOSE_VALUE_CANDIDATE",
            actual_changed_json_pointers=[
                "/data/customer/msisdn",
                "/data/customer/name",
            ],
            declared_changed_json_pointers=[
                "/data/customer/msisdn",
                "/data/customer/name",
            ],
            target_json_pointers=["/data/customer/msisdn"],
        )
    assert error.value.code == AmendmentErrorCode.AMENDMENT_SCOPE_VIOLATION
