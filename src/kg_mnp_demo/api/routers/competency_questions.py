from __future__ import annotations

from fastapi import APIRouter, Depends

from kg_mnp_demo.api.dependencies import AppState, get_state
from kg_mnp_demo.api.schemas.common import ERROR_RESPONSES
from kg_mnp_demo.api.schemas.queries import (
    CompetencyExecuteRequest,
    CompetencyQuestionExecutionResponse,
    CompetencyQuestionListResponse,
    CompetencyQuestionResponse,
)

router = APIRouter()


@router.get(
    "/competency-questions",
    response_model=CompetencyQuestionListResponse,
    responses=ERROR_RESPONSES,
)
def list_cqs(state: AppState = Depends(get_state)):
    return {"items": state.query_service.list_questions()}


@router.get(
    "/competency-questions/{cq_id}",
    response_model=CompetencyQuestionResponse,
    responses=ERROR_RESPONSES,
)
def get_cq(cq_id: str, state: AppState = Depends(get_state)):
    return state.query_service.get_question(cq_id)


@router.post(
    "/competency-questions/{cq_id}/execute",
    response_model=CompetencyQuestionExecutionResponse,
    responses=ERROR_RESPONSES,
)
def execute_cq(
    cq_id: str,
    body: CompetencyExecuteRequest,
    state: AppState = Depends(get_state),
):
    return state.query_service.execute(cq_id, case_id=body.case_id)
