"""Tests for local offline showcase demo."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from kg_mnp_demo.loader import case_path

ROOT = Path(__file__).resolve().parents[1]


def _import_showcase():
    import importlib.util

    path = ROOT / "scripts" / "showcase_demo.py"
    spec = importlib.util.spec_from_file_location("showcase_demo", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def showcase():
    return _import_showcase()


def test_showcase_runs_rdf_offline(showcase, tmp_path):
    code = showcase.main(["--case", "CASE-03", "--output-dir", str(tmp_path), "--no-html"])
    assert code == 0
    assert (tmp_path / "case03_evaluation.json").exists()
    payload = json.loads((tmp_path / "case03_evaluation.json").read_text(encoding="utf-8"))
    assert payload["backend"] == "rdf"
    assert payload["decision"] == "BLOCKED"


def test_case03_contract_block_and_trace(showcase, tmp_path):
    primary = showcase.evaluate_pipeline("CASE-03")
    assert primary["backend"] == "rdf"
    assert primary["evaluation"]["decision"] == "BLOCKED"
    codes = [b["reason_code"] for b in primary["evaluation"]["blocking_reasons"]]
    assert "ACTIVE_CONTRACT_RESTRICTION" in codes

    trace = primary["trace"]
    assert trace
    assert trace["blocking_reasons"]
    row = trace["blocking_reasons"][0]
    assert row["evidence"]
    assert row["ruleId"]
    assert row["ruleVersion"]
    assert row["clauseId"]
    assert row["actionCode"]

    subgraph = trace["subgraph"]
    preds = {e["predicate"] for e in subgraph["edges"]}
    assert "usesEvidence" in preds
    assert "producesBlockingReason" in preds
    assert "recommendsAction" in preds
    assert "triggeredByRuleVersion" in preds
    # No fabricated Evidence→triggeredByRuleVersion edge
    for e in subgraph["edges"]:
        if e["predicate"] == "triggeredByRuleVersion":
            assert "Reason-" in e["source_local"] or "Blocking" in (
                next(
                    (
                        n["type"]
                        for n in subgraph["nodes"]
                        if n["id"] == e["source"]
                    ),
                    "",
                )
                or ""
            )

    chain = trace["human_chains"][0]
    assert chain["evidence_id"]
    assert chain["rule_id"]
    assert chain["rule_version"]
    assert chain["clause_id"]
    assert chain["action_code"]

    assert primary["input_validation"]["status"] == "PASSED"
    assert primary["assessment_validation"]["status"] == "PASSED"


def test_all_cases_summary(showcase):
    summary = showcase.summarize_all_cases()
    assert set(summary["cases"]) == {
        "CASE-01",
        "CASE-02",
        "CASE-03",
        "CASE-04",
        "CASE-05",
        "CASE-06",
    }
    assert summary["cases"]["CASE-01"]["decision"] == "ELIGIBLE"
    assert summary["cases"]["CASE-04"]["blocking_reasons"] == [
        "OUTSTANDING_BALANCE",
        "ACTIVE_CONTRACT_RESTRICTION",
    ] or sorted(summary["cases"]["CASE-04"]["blocking_reasons"]) == [
        "ACTIVE_CONTRACT_RESTRICTION",
        "OUTSTANDING_BALANCE",
    ]
    assert len(summary["cases"]["CASE-04"]["blocking_reasons"]) == 2
    assert summary["cases"]["CASE-05"]["decision"] == "MANUAL_REVIEW"
    assert "MISSING_OR_EXPIRED_EVIDENCE" in summary["cases"]["CASE-05"]["blocking_reasons"]

    case06 = summary["cases"]["CASE-06"]
    assert case06["decision"] == "BLOCKED"
    assert "PORTING_INTERVAL_TOO_SHORT" in case06["blocking_reasons"]
    assert case06["affected_assessments"]
    assert any(
        "ASSESS-CASE-06-HIST" in (r.get("assessmentId") or "")
        for r in case06["affected_assessments"]
    )


def test_html_generated(showcase, tmp_path):
    code = showcase.main(["--output-dir", str(tmp_path)])
    assert code == 0
    html_path = tmp_path / "demo_report.html"
    assert html_path.exists()
    text = html_path.read_text(encoding="utf-8")
    assert "KG-MNP 携号转网资格判断领域本体演示" in text
    assert "BLOCKED" in text
    assert "ACTIVE_CONTRACT_RESTRICTION" in text
    assert "资格判断追溯子图" in text
    assert "producesBlockingReason" in text or "usesEvidence" in text
    assert "triggeredByRuleVersion" in text  # real predicate on BlockingReason
    assert "完整追溯链" not in text


def test_what_if_does_not_modify_ttl(showcase):
    ttl = case_path("CASE-03")
    before = ttl.read_bytes()
    before_hash = hashlib.sha256(before).hexdigest()

    result = showcase.evaluate_pipeline("CASE-03", what_if="contract-expired")
    after = ttl.read_bytes()
    after_hash = hashlib.sha256(after).hexdigest()

    assert before_hash == after_hash
    assert result["ttl_unchanged"] is True
    assert result["evaluation"]["decision"] == "ELIGIBLE"


def test_showcase_repeatable(showcase, tmp_path):
    a = showcase.evaluate_pipeline("CASE-03")
    b = showcase.evaluate_pipeline("CASE-03")
    assert a["evaluation"]["decision"] == b["evaluation"]["decision"]
    assert [x["reason_code"] for x in a["evaluation"]["blocking_reasons"]] == [
        x["reason_code"] for x in b["evaluation"]["blocking_reasons"]
    ]

    showcase.main(["--output-dir", str(tmp_path / "r1"), "--no-html"])
    showcase.main(["--output-dir", str(tmp_path / "r2"), "--no-html"])
    e1 = json.loads((tmp_path / "r1" / "case03_evaluation.json").read_text(encoding="utf-8"))
    e2 = json.loads((tmp_path / "r2" / "case03_evaluation.json").read_text(encoding="utf-8"))
    assert e1["decision"] == e2["decision"]
    assert e1["blocking_reasons"] == e2["blocking_reasons"]


def test_cli_default_backend_is_rdf():
    from kg_mnp_demo.cli import _default_backend

    assert _default_backend() in ("rdf", "neo4j")
    # Without env override in this process we expect rdf after the change;
    # if KG_MNP_BACKEND is set in the environment, honour it.
    import os

    old = os.environ.pop("KG_MNP_BACKEND", None)
    try:
        assert _default_backend() == "rdf"
    finally:
        if old is not None:
            os.environ["KG_MNP_BACKEND"] = old
