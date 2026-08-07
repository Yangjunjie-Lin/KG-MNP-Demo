from __future__ import annotations

import copy
import json

import pytest

from kg_mnp_demo.graphdb.verifier import (
    GraphDBVerificationError,
    assert_review_audit_semantics,
    expected_review_audit_rows,
    normalize_select_result,
)

from ._helpers import ROOT


def _expected():
    suite = json.loads(
        (
            ROOT
            / "examples/graphdb/expected/full-confirmation/verification/query-suite-manifest.json"
        ).read_text(encoding="utf-8")
    )
    return suite["expected"]["review_audit"]


def test_review_audit_exact_authority_rows_pass():
    expected = _expected()
    assert_review_audit_semantics(expected_review_audit_rows(expected), expected)


def test_removing_one_review_decision_fails_even_if_other_structure_remains():
    expected = _expected()
    rows = expected_review_audit_rows(expected)

    with pytest.raises(GraphDBVerificationError, match="review audit"):
        assert_review_audit_semantics(rows[:-1], expected)


def test_same_decision_count_with_wrong_subject_fails():
    expected = _expected()
    rows = copy.deepcopy(expected_review_audit_rows(expected))
    rows[0]["subject"]["value"] = "urn:attack:replacement-subject"

    with pytest.raises(GraphDBVerificationError, match="review audit"):
        assert_review_audit_semantics(rows, expected)


def test_graphdb_datetime_utc_offset_is_normalized_to_source_z_lexical():
    normalized = normalize_select_result(
        {
            "head": {"vars": ["decidedAt"]},
            "results": {
                "bindings": [
                    {
                        "decidedAt": {
                            "type": "literal",
                            "value": "2026-08-06T00:03:00+00:00",
                            "datatype": "http://www.w3.org/2001/XMLSchema#dateTime",
                        }
                    }
                ]
            },
        }
    )

    assert normalized["results"]["bindings"][0]["decidedAt"]["value"] == (
        "2026-08-06T00:03:00Z"
    )
