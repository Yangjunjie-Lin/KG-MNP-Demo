"""Modeling status vocabulary tests."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "modeling-statuses.yaml"


def _load() -> dict:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


REQUIRED = {
    "review_status": {"PROPOSED", "CONFIRMED", "REJECTED", "DEPRECATED"},
    "review_decision": {
        "CONFIRM",
        "REJECT",
        "MODIFY_AND_CONFIRM",
        "DEFER",
        "DEPRECATE",
    },
    "issue_types": {
        "MISSING_INFORMATION",
        "CONFLICT",
        "AMBIGUOUS",
        "UNSUPPORTED",
        "INCONSISTENT_SOURCE",
        "LOW_CONFIDENCE",
    },
    "publication_scope": {
        "TBOX",
        "ABOX",
        "EVIDENCE",
        "MAPPING",
        "REVIEW_ONLY",
        "NONE",
    },
}


def test_required_vocabularies_present():
    data = _load()
    for key, expected in REQUIRED.items():
        assert key in data
        values = data[key]
        assert isinstance(values, list)
        assert values
        assert all(isinstance(item, str) and item.strip() for item in values)
        assert len(values) == len(set(values))
        assert set(values) == expected


def test_no_cross_vocabulary_mixing():
    data = _load()
    review_status = set(data["review_status"])
    review_decision = set(data["review_decision"])
    issue_types = set(data["issue_types"])
    publication_scope = set(data["publication_scope"])

    assert "DEFER" not in review_status
    assert "MISSING_INFORMATION" not in review_status
    assert "CONFIRMED" not in issue_types
    assert "TBOX" not in review_status
    assert review_status.isdisjoint(issue_types)
    assert review_status.isdisjoint(publication_scope)
    assert review_decision.isdisjoint(issue_types)
    assert review_decision.isdisjoint(publication_scope)
