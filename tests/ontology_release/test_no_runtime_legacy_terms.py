"""Gate current assets against the occurrence-exact legacy-term policy."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_runtime_legacy_terms as checker  # noqa: E402


def test_no_unapproved_runtime_legacy_terms():
    result = checker.audit_repository()
    assert result.ok, "\n".join(result.errors)


def test_legacy_allowlist_is_occurrence_exact():
    policy = checker.load_policy()
    required_roots = {
        "src",
        "ontology",
        "shapes",
        "examples",
        "data",
        "queries",
        "competency_questions",
        "mappings",
        "rules",
        "tests",
        "scripts",
        "demo_outputs",
    }
    assert required_roots <= set(policy.scan_roots)
    assert policy.allowances
    assert all(allowance.path and allowance.line_text for allowance in policy.allowances)
    assert all(allowance.count >= 1 for allowance in policy.allowances)
    assert all(allowance.reason for allowance in policy.allowances)
    assert all("*" not in allowance.path for allowance in policy.allowances)
    assert checker.REQUIRED_LEGACY_TERMS <= set(policy.terms)
