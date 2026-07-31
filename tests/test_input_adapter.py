"""Tests for JSON input adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kg_mnp_demo.input_adapter import InputValidationError, load_and_normalize, normalize_case_input

ROOT = Path(__file__).resolve().parents[1]


def test_valid_case03_passes_schema():
    data = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
    normalized = normalize_case_input(data)
    assert normalized.case_id == "CASE-03"
    assert normalized.contract.contract_status == "ACTIVE"


def test_missing_source_system_rejected():
    with pytest.raises(InputValidationError) as exc:
        load_and_normalize(ROOT / "inputs" / "invalid_missing_source.json")
    joined = "; ".join(exc.value.errors)
    assert "source_system" in joined
    assert "evidence.identity" in joined


def test_bad_datetime_rejected():
    data = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
    data["evidence"]["contract"]["contract_end_time"] = "not-a-date"
    with pytest.raises(InputValidationError) as exc:
        normalize_case_input(data)
    assert any("date-time" in e for e in exc.value.errors)
