"""Structural quality metrics and deterministic gate construction."""

from __future__ import annotations

from typing import Any

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.registry import validate_contract

METRICS = (
    ("source-integrity", "EXACT_STRUCTURAL_CHECK"),
    ("parse-success", "EXACT_STRUCTURAL_CHECK"),
    ("structural-validity", "EXACT_STRUCTURAL_CHECK"),
    ("locator-validity", "EXACT_STRUCTURAL_CHECK"),
    ("evidence-coverage", "COVERAGE_CHECK"),
    ("transformation-traceability", "COVERAGE_CHECK"),
    ("normalization-consistency", "POLICY_CHECK"),
    ("content-coverage", "COVERAGE_CHECK"),
)


def preview_quality_report_id(subject_id: str, issues: tuple[str, ...]) -> str:
    return stable_urn("quality-report", {"subject_id": subject_id, "issues": sorted(set(issues)), "profile": "structural-v1"})


def build_quality_report(
    *,
    subject_id: str,
    item_count: int,
    evidence_count: int,
    issues: tuple[str, ...],
) -> dict[str, Any]:
    issue_codes = sorted(set(issues))
    fail_prefixes = ("HASH_", "PATH_", "ZIP_", "CONTRACT_", "PARSE_", "ARTIFACT_")
    fail = [item for item in issue_codes if item.startswith(fail_prefixes)]
    gate_status = "FAIL" if fail else "REVIEW_REQUIRED" if issue_codes else "PASS"
    metric_issues = [
        {"code": code, "message": code.replace("_", " ").title(), "severity": "ERROR" if code in fail else "WARNING"}
        for code in issue_codes
    ]
    metrics = []
    for metric_id, basis in METRICS:
        denominator = item_count if metric_id == "evidence-coverage" else max(evidence_count, 1)
        numerator = denominator if gate_status != "FAIL" else 0
        metrics.append({
            "metric_id": metric_id,
            "measurement_basis": basis,
            "numerator": numerator,
            "denominator": denominator,
            "score_basis_points": 10000 if numerator == denominator else 0,
            "status": gate_status,
            "issues": metric_issues if metric_id in {"parse-success", "content-coverage"} else [],
        })
    core = {
        "manifest_kind": "KG_MNP_QUALITY_REPORT",
        "schema_version": "1.0.0",
        "quality_report_id": preview_quality_report_id(subject_id, tuple(issue_codes)),
        "subject_id": subject_id,
        "metrics": metrics,
        "gate_status": gate_status,
        "issues": metric_issues,
    }
    report = {**core, "content_digest": semantic_hash(core)}
    validate_contract("quality-report", report)
    return report
