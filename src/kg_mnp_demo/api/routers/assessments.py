from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from kg_mnp_demo.api.schemas.common import ERROR_RESPONSES, ErrorResponse
from kg_mnp_demo.api.dependencies import AppState, get_state
from kg_mnp_demo.api.schemas.assessment import (
    AssessmentCreateRequest,
    AssessmentListResponse,
    AssessmentRecordResponse,
    AssessmentResponse,
    ArtifactsResponse,
    ComparisonResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from kg_mnp_demo.application.assessment_service import write_assessment_artifacts
from kg_mnp_demo.application.errors import ApplicationError
from kg_mnp_demo.application.serializers import to_iso_utc
from kg_mnp_demo.input_adapter import InputValidationError, normalize_case_input
from kg_mnp_demo.storage import compute_input_hash

router = APIRouter()


def _payload_dict(body: AssessmentCreateRequest) -> dict[str, Any]:
    return body.payload.to_pipeline_dict()


@router.post(
    "/assessments",
    response_model=AssessmentResponse,
    responses=ERROR_RESPONSES,
)
def create_assessment(
    body: AssessmentCreateRequest,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    payload = _payload_dict(body)
    try:
        normalized = normalize_case_input(payload)
    except InputValidationError as exc:
        raise ApplicationError("INPUT_SCHEMA_ERROR", details=list(exc.errors)) from exc

    assessment_time = to_iso_utc(normalized.assessment_time) or ""
    input_hash = compute_input_hash(payload)

    if body.persist and not body.force_recompute:
        existing = state.repository.find_idempotent_execution(
            normalized.case_id, assessment_time, input_hash
        )
        if existing:
            return existing.get("result") or existing

    execution_id = str(uuid.uuid4())
    execution = state.assessment_service.assess_execution(
        payload,
        persist_artifacts=False,
        execution_id=execution_id,
    )
    result = execution.response

    if not body.persist:
        return result

    art_dir_name = None
    wrote_artifacts = False
    try:
        if result.get("case_id") and result.get("assessment_time"):
            out = state.artifacts.execution_dir(execution_id)
            names = write_assessment_artifacts(execution, out, write_html=False)
            result["artifacts"] = state.artifacts.relative_artifacts(names)
            art_dir_name = out.name
            wrote_artifacts = True
        record = state.repository.save_execution(
            execution_id=result["execution_id"],
            case_id=result["case_id"],
            assessment_time=result["assessment_time"],
            input_payload=payload,
            result=result,
            artifact_directory=art_dir_name,
            force_recompute=body.force_recompute,
        )
        saved = record.get("result") or result
        # If idempotent path somehow returned older id, drop orphaned dir
        if (
            wrote_artifacts
            and record.get("execution_id")
            and record["execution_id"] != execution_id
        ):
            state.artifacts.cleanup_execution_dir(execution_id)
        return saved
    except Exception:
        if wrote_artifacts:
            state.artifacts.cleanup_execution_dir(execution_id)
        raise


@router.get(
    "/assessments",
    response_model=AssessmentListResponse,
    responses=ERROR_RESPONSES,
)
def list_assessments(
    case_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    state: AppState = Depends(get_state),
):
    return {
        "items": state.repository.list_executions(
            case_id=case_id, limit=limit, offset=offset
        )
    }


@router.get(
    "/assessments/compare",
    response_model=ComparisonResponse,
    responses=ERROR_RESPONSES,
)
def compare_assessments(
    left: str,
    right: str,
    state: AppState = Depends(get_state),
):
    return state.repository.compare_executions(left, right)


@router.get(
    "/assessments/{execution_id}",
    response_model=AssessmentRecordResponse,
    responses=ERROR_RESPONSES,
)
def get_assessment(execution_id: str, state: AppState = Depends(get_state)):
    return state.repository.get_execution(execution_id)


@router.get(
    "/assessments/{execution_id}/trace",
    responses=ERROR_RESPONSES,
)
def get_trace(execution_id: str, state: AppState = Depends(get_state)):
    record = state.repository.get_execution(execution_id)
    result = record.get("result") or {}
    return result.get("trace_subgraph") or {"nodes": [], "edges": []}


@router.get(
    "/assessments/{execution_id}/artifacts",
    response_model=ArtifactsResponse,
    responses=ERROR_RESPONSES,
)
def get_artifacts(execution_id: str, state: AppState = Depends(get_state)):
    record = state.repository.get_execution(execution_id)
    result = record.get("result") or {}
    return {"execution_id": execution_id, "artifacts": result.get("artifacts") or {}}


@router.post(
    "/assessments/{execution_id}/what-if",
    response_model=WhatIfResponse,
    responses=ERROR_RESPONSES,
)
def assessment_what_if(
    execution_id: str,
    body: WhatIfRequest,
    state: AppState = Depends(get_state),
):
    record = state.repository.get_execution(execution_id)
    baseline = record.get("input") or {}
    return state.assessment_service.run_what_if(baseline, body.changes)
