from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from kg_mnp_demo.api.dependencies import AppState, get_state
from kg_mnp_demo.api.schemas.assessment import (
    AssessmentCreateRequest,
    AssessmentListResponse,
    AssessmentRecordResponse,
    AssessmentResponse,
    ArtifactsResponse,
    ComparisonResponse,
    TraceGraphResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from kg_mnp_demo.api.schemas.common import ERROR_RESPONSES
from kg_mnp_demo.application.persist import persist_assessment

router = APIRouter()


@router.post(
    "/assessments",
    response_model=AssessmentResponse,
    responses=ERROR_RESPONSES,
)
def create_assessment(
    body: AssessmentCreateRequest,
    state: AppState = Depends(get_state),
) -> dict[str, Any]:
    payload = body.payload.to_pipeline_dict()
    return persist_assessment(
        payload=payload,
        repository=state.repository,
        artifacts=state.artifacts,
        assessment_service=state.assessment_service,
        persist=body.persist,
        force_recompute=body.force_recompute,
    )


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
    response_model=TraceGraphResponse,
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
