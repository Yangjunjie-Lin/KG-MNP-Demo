from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query

from kg_mnp_demo.api.dependencies import get_state
from kg_mnp_demo.api.schemas.assessment import AssessmentCreateRequest, WhatIfRequest
from kg_mnp_demo.application.assessment_service import write_assessment_artifacts
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode

router = APIRouter()


@router.post("/assessments")
def create_assessment(body: AssessmentCreateRequest) -> dict[str, Any]:
    state = get_state()
    execution_id = str(uuid.uuid4())
    try:
        execution = state.assessment_service.assess_execution(
            body.payload,
            persist_artifacts=False,
            execution_id=execution_id,
        )
    except ApplicationError:
        raise

    result = execution.response
    if body.persist and result.get("case_id") and result.get("assessment_time"):
        art_dir = None
        if execution.exit_code == 0 or result.get("decision") is not None:
            out = state.artifacts.execution_dir(execution_id)
            names = write_assessment_artifacts(execution, out, write_html=False)
            result["artifacts"] = state.artifacts.relative_artifacts(names)
            art_dir = out.name
        record = state.repository.save_execution(
            execution_id=result["execution_id"],
            case_id=result["case_id"],
            assessment_time=result["assessment_time"],
            input_payload=body.payload,
            result=result,
            artifact_directory=art_dir,
            force_recompute=body.force_recompute,
        )
        return record.get("result") or result
    return result


@router.get("/assessments")
def list_assessments(
    case_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return {"items": get_state().repository.list_executions(case_id=case_id, limit=limit, offset=offset)}


@router.get("/assessments/compare")
def compare_assessments(left: str, right: str):
    return get_state().repository.compare_executions(left, right)


@router.get("/assessments/{execution_id}")
def get_assessment(execution_id: str):
    return get_state().repository.get_execution(execution_id)


@router.get("/assessments/{execution_id}/trace")
def get_trace(execution_id: str):
    record = get_state().repository.get_execution(execution_id)
    result = record.get("result") or {}
    return result.get("trace_subgraph") or {"nodes": [], "edges": []}


@router.get("/assessments/{execution_id}/artifacts")
def get_artifacts(execution_id: str):
    record = get_state().repository.get_execution(execution_id)
    result = record.get("result") or {}
    return {"execution_id": execution_id, "artifacts": result.get("artifacts") or {}}


@router.post("/assessments/{execution_id}/what-if")
def assessment_what_if(execution_id: str, body: WhatIfRequest):
    state = get_state()
    record = state.repository.get_execution(execution_id)
    baseline = record.get("input") or {}
    return state.assessment_service.run_what_if(baseline, body.changes)
