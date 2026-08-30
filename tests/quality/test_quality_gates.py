from __future__ import annotations

import json

from kg_mnp.ingestion.quality import build_quality_report

SUBJECT_ID = "urn:kg-mnp:ingestion-run:" + "1" * 64


def test_pass_review_and_fail_quality_gates_are_structural() -> None:
    passed = build_quality_report(subject_id=SUBJECT_ID, item_count=2, evidence_count=2, issues=())
    review = build_quality_report(
        subject_id=SUBJECT_ID,
        item_count=2,
        evidence_count=2,
        issues=("MISSING_OCR_OR_VISION_PROVIDER",),
    )
    failed = build_quality_report(
        subject_id=SUBJECT_ID,
        item_count=2,
        evidence_count=1,
        issues=("HASH_MISMATCH",),
    )
    assert passed["gate_status"] == "PASS"
    assert review["gate_status"] == "REVIEW_REQUIRED"
    assert failed["gate_status"] == "FAIL"
    assert all(
        metric["measurement_basis"]
        in {"EXACT_STRUCTURAL_CHECK", "COVERAGE_CHECK", "POLICY_CHECK"}
        for metric in passed["metrics"]
    )
    assert all(metric["measurement_basis"] != "GROUND_TRUTH_COMPARISON" for metric in passed["metrics"])


def test_quality_issue_order_and_ids_are_deterministic() -> None:
    left = build_quality_report(
        subject_id=SUBJECT_ID,
        item_count=1,
        evidence_count=1,
        issues=("PDF_TEXT_ORDER_UNCERTAIN", "MISSING_OCR_OR_VISION_PROVIDER"),
    )
    right = build_quality_report(
        subject_id=SUBJECT_ID,
        item_count=1,
        evidence_count=1,
        issues=("MISSING_OCR_OR_VISION_PROVIDER", "PDF_TEXT_ORDER_UNCERTAIN"),
    )
    assert left == right
    assert [item["code"] for item in left["issues"]] == sorted(
        item["code"] for item in left["issues"]
    )


def test_quality_metrics_do_not_claim_fake_accuracy() -> None:
    report = build_quality_report(
        subject_id=SUBJECT_ID, item_count=3, evidence_count=3, issues=()
    )
    assert {metric["metric_id"] for metric in report["metrics"]} == {
        "source-integrity",
        "parse-success",
        "structural-validity",
        "locator-validity",
        "evidence-coverage",
        "transformation-traceability",
        "normalization-consistency",
        "content-coverage",
    }
    assert "accuracy" not in json.dumps(report, sort_keys=True).casefold()
