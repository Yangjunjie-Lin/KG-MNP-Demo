from __future__ import annotations

import copy
import json

import pytest

from kg_mnp_demo.graphdb.verifier import (
    GraphDBVerificationError,
    assert_tbox_version_semantics,
    expected_tbox_version_rows,
)

from ._helpers import ROOT


def _expected():
    suite = json.loads(
        (
            ROOT
            / "examples/graphdb/expected/full-confirmation/verification/query-suite-manifest.json"
        ).read_text(encoding="utf-8")
    )
    return suite["expected"]["tbox_versions"]


def test_exact_graph_ontology_version_and_module_set_passes():
    expected = _expected()
    assert_tbox_version_semantics(expected_tbox_version_rows(expected), expected)


def test_same_count_with_replaced_version_iri_fails():
    expected = _expected()
    rows = copy.deepcopy(expected_tbox_version_rows(expected))
    rows[0]["version"]["value"] = "urn:attack:wrong-version"

    with pytest.raises(GraphDBVerificationError, match="TBox"):
        assert_tbox_version_semantics(rows, expected)
