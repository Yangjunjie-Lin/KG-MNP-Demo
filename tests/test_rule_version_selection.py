"""Time-aware eligibility rule version selection."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from kg_mnp_demo.evaluator import evaluate_case
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph, rules_path
from kg_mnp_demo.rule_engine import (
    RuleConfigurationError,
    load_applicable_rules,
    validate_rule_configuration,
)

ROOT = Path(__file__).resolve().parents[1]


def _at(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _port_version(as_of: datetime) -> str:
    rules = load_applicable_rules(as_of)
    port = next(r for r in rules if r["rule_id"] == "MNP-ELIG-005")
    return str(port["version"])


def test_version_boundaries():
    assert _port_version(_at("2026-05-31T23:59:59Z")) == "1.0"
    assert _port_version(_at("2026-06-01T00:00:00Z")) == "1.1"
    assert _port_version(_at("2025-01-01T00:00:00Z")) == "1.0"
    assert _port_version(_at("2027-01-01T00:00:00Z")) == "1.1"


def test_overlap_raises():
    catalog = yaml.safe_load(rules_path().read_text(encoding="utf-8"))
    rules = list(catalog["rules"]) + list(catalog["rule_updates"])
    # Force overlap on ELIG-005
    for r in rules:
        if r["rule_id"] == "MNP-ELIG-005" and str(r["version"]) == "1.0":
            r["effective_to"] = "2026-06-15T00:00:00Z"
    with pytest.raises(RuleConfigurationError, match="Overlapping"):
        validate_rule_configuration(rules)


def test_no_applicable_version_raises():
    with pytest.raises(RuleConfigurationError, match="No applicable"):
        load_applicable_rules(_at("2020-01-01T00:00:00Z"))


def test_effective_to_before_from_fails():
    catalog = yaml.safe_load(rules_path().read_text(encoding="utf-8"))
    rules = list(catalog["rules"]) + list(catalog["rule_updates"])
    for r in rules:
        if r["rule_id"] == "MNP-ELIG-001":
            r["effective_to"] = "2023-01-01T00:00:00Z"
            break
    with pytest.raises(RuleConfigurationError, match="effective_to < effective_from"):
        validate_rule_configuration(rules)


def test_default_cases_unchanged():
    g = load_case_graph("CASE-03")
    apply_owlrl(g)
    result = evaluate_case(g, "CASE-03", validate=False)
    assert result["decision"] == "BLOCKED"
    assert result["blocking_reasons"][0]["reason_code"] == "ACTIVE_CONTRACT_RESTRICTION"
    port = next(r for r in result["rules"] if r["rule_id"] == "MNP-ELIG-005")
    assert port["version"] == "1.1"
    assert port["effective_from"]
    assert port["selected_for_assessment_time"] == "2026-07-01T00:00:00Z"


def test_case06_hist_and_current_versions():
    g = load_case_graph("CASE-06")
    apply_owlrl(g)
    result = evaluate_case(g, "CASE-06", validate=False)
    assert result["decision"] == "BLOCKED"
    port = next(r for r in result["rules"] if r["rule_id"] == "MNP-ELIG-005")
    assert port["version"] == "1.1"

    # Historical assessment time selects v1.0
    g2 = load_case_graph("CASE-06")
    apply_owlrl(g2)
    hist = evaluate_case(
        g2,
        "CASE-06",
        assessment_time=_at("2026-05-15T12:00:00Z"),
        validate=False,
    )
    port_hist = next(r for r in hist["rules"] if r["rule_id"] == "MNP-ELIG-005")
    assert port_hist["version"] == "1.0"
    assert hist["decision"] == "ELIGIBLE"


def test_json_assessment_time_selects_version(tmp_path):
    from kg_mnp_demo.pipeline import run_pipeline
    import json

    data = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
    data["assessment_time"] = "2026-05-15T00:00:00Z"
    path = tmp_path / "early.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    result = run_pipeline(path, tmp_path / "out", write_html=False)
    port = next(r for r in result["evaluation"]["rules"] if r["rule_id"] == "MNP-ELIG-005")
    assert port["version"] == "1.0"


def test_selection_repeatable():
    a = load_applicable_rules(_at("2026-07-01T00:00:00Z"))
    b = load_applicable_rules(_at("2026-07-01T00:00:00Z"))
    assert [(r["rule_id"], r["version"]) for r in a] == [
        (r["rule_id"], r["version"]) for r in b
    ]


def test_blocking_reason_records_validity():
    g = load_case_graph("CASE-03")
    apply_owlrl(g)
    result = evaluate_case(g, "CASE-03", validate=False)
    reason = result["blocking_reasons"][0]
    assert reason["effective_from"]
    assert reason["assessment_time"] == "2026-07-01T00:00:00Z"
