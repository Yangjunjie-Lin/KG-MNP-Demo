"""Structural quality evaluator; never reports unmeasured semantic accuracy."""

from kg_mnp.plugins.models import QualityEvaluationRequest, QualityEvaluationResult


class StructuralQualityEvaluator:
    def evaluate(self, request: QualityEvaluationRequest) -> QualityEvaluationResult:
        issues = set(request.unresolved_issues)
        for unit in request.units:
            issues.update(unit.quality_flags)
        fail = {item for item in issues if item.startswith(("HASH_", "PATH_", "ZIP_", "CONTRACT_", "PARSE_"))}
        review = issues - fail
        status = "FAIL" if fail else "REVIEW_REQUIRED" if review else "PASS"
        return QualityEvaluationResult(status, tuple(sorted(issues)))
