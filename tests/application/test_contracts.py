"""Contract shape and serializer tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from kg_mnp_demo.application.contracts import (
    ASSESSMENT_RESPONSE_KEYS,
    SCHEMA_VERSION,
    build_assessment_response,
)
from kg_mnp_demo.application.serializers import deep_merge, json_safe, to_iso_utc


def test_build_assessment_response_keys():
    payload = build_assessment_response(
        execution_id="e1",
        case_id="CASE-03",
        assessment_time="2026-07-01T00:00:00Z",
        decision="BLOCKED",
        publication={"publishable": True, "status": "PUBLISHABLE"},
        validations={},
    )
    assert list(payload.keys()) == list(ASSESSMENT_RESPONSE_KEYS)
    assert payload["schema_version"] == SCHEMA_VERSION
    json.dumps(payload)


def test_json_safe_types():
    raw = {
        "when": datetime(2026, 7, 1, tzinfo=timezone.utc),
        "amount": Decimal("12.50"),
        "path": Path("/tmp/secret/file.json"),
    }
    safe = json_safe(raw)
    assert safe["when"] == "2026-07-01T00:00:00Z"
    assert safe["amount"] == "12.50"
    assert safe["path"] == "file.json"
    assert "/" not in safe["path"] or safe["path"] == "file.json"
    json.dumps(safe)


def test_to_iso_utc():
    assert to_iso_utc(datetime(2026, 7, 1, tzinfo=timezone.utc)) == "2026-07-01T00:00:00Z"


def test_deep_merge():
    base = {"a": 1, "evidence": {"contract": {"status": "ACTIVE", "x": 1}}}
    changes = {"evidence": {"contract": {"status": "EXPIRED"}}}
    merged = deep_merge(base, changes)
    assert merged["evidence"]["contract"]["status"] == "EXPIRED"
    assert merged["evidence"]["contract"]["x"] == 1
    assert base["evidence"]["contract"]["status"] == "ACTIVE"
