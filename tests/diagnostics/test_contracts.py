from __future__ import annotations

import pytest

from kg_mnp_demo.diagnostics.contracts import (
    strict_json_bytes,
    validate_diagnostic_contract,
)
from kg_mnp_demo.diagnostics.policy import (
    DiagnosticClassification,
    DiagnosticSeverity,
    load_diagnostic_policy,
)


def test_policy_is_versioned_and_closed() -> None:
    policy = load_diagnostic_policy()
    assert policy["policy_version"] == "1.0.0"
    assert set(policy["classifications"]) == {
        item.value for item in DiagnosticClassification
    }
    assert {value["severity"] for value in policy["classifications"].values()} <= {
        item.value for item in DiagnosticSeverity
    }


def test_duplicate_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        strict_json_bytes(b'{"a": 1, "A": 2}')


def test_issue_schema_rejects_untrusted_extra_fields() -> None:
    with pytest.raises(ValueError):
        validate_diagnostic_contract("diagnostic-issue", {"unexpected": True})
