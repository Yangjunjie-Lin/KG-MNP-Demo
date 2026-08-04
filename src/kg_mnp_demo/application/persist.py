"""Persist assessment executions with idempotency and safe artifact lifecycle."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from kg_mnp_demo.application.assessment_service import (
    AssessmentService,
    write_assessment_artifacts,
)
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.serializers import to_iso_utc
from kg_mnp_demo.input_adapter import InputValidationError, normalize_case_input
from kg_mnp_demo.storage import (
    AssessmentRepository,
    ArtifactRepository,
    compute_input_hash,
)


logger = logging.getLogger(__name__)


def _cleanup_artifact_dir_best_effort(
    artifacts: ArtifactRepository,
    execution_id: str,
    *,
    reason: str,
) -> None:
    """Clean an uncommitted/replaced artifact without masking the real error."""
    try:
        artifacts.cleanup_execution_dir(execution_id)
    except Exception as exc:  # noqa: BLE001 - cleanup is compensating work
        logger.warning(
            "Artifact cleanup failed (%s) for execution %s: %s",
            reason,
            execution_id,
            exc,
        )


def persist_assessment(
    *,
    payload: dict[str, Any],
    repository: AssessmentRepository,
    artifacts: ArtifactRepository,
    assessment_service: AssessmentService | None = None,
    persist: bool = True,
    force_recompute: bool = False,
    write_html: bool = False,
) -> dict[str, Any]:
    """Run assessment and optionally persist with artifact cleanup semantics.

    force_recompute=true replaces the prior idempotent DB row and removes the
    previous artifact directory only after the new record is saved successfully.
    """
    try:
        normalized = normalize_case_input(payload)
    except InputValidationError as exc:
        raise ApplicationError(
            ErrorCode.INPUT_SCHEMA_ERROR, details=list(exc.errors)
        ) from exc

    assessment_time = to_iso_utc(normalized.assessment_time) or ""
    input_hash = compute_input_hash(payload)
    service = assessment_service or AssessmentService()

    existing = repository.find_idempotent_execution(
        normalized.case_id, assessment_time, input_hash
    )
    if persist and existing and not force_recompute:
        return existing.get("result") or existing

    old_execution_id = existing.get("execution_id") if existing else None
    old_artifact_dir = existing.get("artifact_directory") if existing else None

    execution_id = str(uuid.uuid4())
    execution = service.assess_execution(
        payload,
        persist_artifacts=False,
        execution_id=execution_id,
    )
    result = execution.response

    if not persist:
        return result

    art_dir_name: str | None = None
    wrote_artifacts = False
    try:
        if result.get("case_id") and result.get("assessment_time"):
            out = artifacts.execution_dir(execution_id)
            # Mark the directory as owned by this attempt before writing any
            # files so a partial artifact is also compensated on failure.
            wrote_artifacts = True
            names = write_assessment_artifacts(execution, out, write_html=write_html)
            result["artifacts"] = artifacts.relative_artifacts(names)
            art_dir_name = out.name

        record = repository.save_execution(
            execution_id=result["execution_id"],
            case_id=result["case_id"],
            assessment_time=result["assessment_time"],
            input_payload=payload,
            result=result,
            artifact_directory=art_dir_name,
            force_recompute=force_recompute,
        )
        saved = record.get("result") or result

        # After successful replace, remove previous artifact for same idempotent key.
        if (
            force_recompute
            and old_execution_id
            and old_execution_id != result["execution_id"]
        ):
            _cleanup_artifact_dir_best_effort(
                artifacts,
                old_execution_id,
                reason="replaced execution",
            )
            if old_artifact_dir and old_artifact_dir != old_execution_id:
                _cleanup_artifact_dir_best_effort(
                    artifacts,
                    old_artifact_dir,
                    reason="replaced artifact directory",
                )

        # Idempotent race returned older id — drop orphaned new dir.
        if (
            wrote_artifacts
            and record.get("execution_id")
            and record["execution_id"] != execution_id
        ):
            _cleanup_artifact_dir_best_effort(
                artifacts,
                execution_id,
                reason="idempotent race",
            )

        return saved
    except Exception:
        if wrote_artifacts:
            _cleanup_artifact_dir_best_effort(
                artifacts,
                execution_id,
                reason="persistence failure",
            )
        raise


def find_orphan_artifacts(
    repository: AssessmentRepository,
    artifact_repository: ArtifactRepository,
) -> dict[str, list[str]]:
    """Compare DB artifact directories with disk under the artifact root."""
    summaries = repository.list_executions(limit=10000, offset=0)
    known: set[str] = set()
    missing: list[str] = []
    for item in summaries:
        name = item.get("artifact_directory")
        eid = item.get("execution_id")
        if name:
            known.add(str(name))
            path = artifact_repository.root / str(name)
            if not path.is_dir():
                missing.append(str(name))
        if eid:
            known.add(str(eid))

    orphans: list[str] = []
    root = artifact_repository.root
    if root.is_dir():
        for child in sorted(root.iterdir()):
            if child.is_dir() and child.name not in known:
                # Also accept dirs that match an execution_id even if artifact_directory unset
                orphans.append(child.name)
    return {"orphan_directories": orphans, "missing_directories": missing}


def assert_execution_consistency(result: dict[str, Any]) -> None:
    """Raise AssertionError when decision / rules / reasons / times contradict."""
    decision = result.get("decision")
    rules = result.get("rule_results") or []
    reasons = result.get("blocking_reasons") or []
    assessment_time = result.get("assessment_time") or ""

    if decision == "BLOCKED" and not reasons:
        raise AssertionError("BLOCKED assessment must have at least one blocking reason")
    if decision == "ELIGIBLE" and reasons:
        raise AssertionError("ELIGIBLE assessment must not have eligibility blocking reasons")

    fail_rules = {
        (r.get("rule_id"), str(r.get("version") or r.get("rule_version") or ""))
        for r in rules
        if r.get("status") == "FAIL"
    }
    for reason in reasons:
        rid = reason.get("rule_id")
        # Blocking reasons should correspond to a FAIL rule when rule_id present
        if rid and all(r.get("rule_id") == rid and r.get("status") == "PASS" for r in rules if r.get("rule_id") == rid):
            raise AssertionError(
                f"BlockingReason {reason.get('reason_code')} for PASS rule {rid}"
            )

    for ev in result.get("evidence") or []:
        gen = str(ev.get("generated_at") or "")
        if gen and assessment_time and gen.replace("+00:00", "Z") > assessment_time.replace("+00:00", "Z"):
            raise AssertionError(
                f"evidence generated_at {gen} later than assessment_time {assessment_time}"
            )

    for rule in rules:
        selected = rule.get("selected_for_assessment_time")
        if selected and assessment_time:
            # Selected window marker must match assessment time when present
            if selected.replace("+00:00", "Z") != assessment_time.replace("+00:00", "Z"):
                raise AssertionError(
                    f"rule {rule.get('rule_id')} selected_for_assessment_time mismatch"
                )
        # Effective window must cover assessment_time when both ends known
        ef = rule.get("effective_from")
        et = rule.get("effective_to")
        at = assessment_time.replace("+00:00", "Z")
        if ef and at and ef.replace("+00:00", "Z") > at:
            raise AssertionError(f"rule {rule.get('rule_id')} effective_from after assessment_time")
        if et and at and et.replace("+00:00", "Z") < at:
            raise AssertionError(f"rule {rule.get('rule_id')} effective_to before assessment_time")

    _ = fail_rules  # reserved for future stricter cross-checks
