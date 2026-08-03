from __future__ import annotations

from fastapi import APIRouter

from kg_mnp_demo.api.dependencies import get_state
from kg_mnp_demo.api.schemas.queries import CompetencyExecuteRequest

router = APIRouter()


@router.get("/competency-questions")
def list_cqs():
    return {"items": get_state().query_service.list_questions()}


@router.get("/competency-questions/{cq_id}")
def get_cq(cq_id: str):
    return get_state().query_service.get_question(cq_id)


@router.post("/competency-questions/{cq_id}/execute")
def execute_cq(cq_id: str, body: CompetencyExecuteRequest):
    return get_state().query_service.execute(cq_id, case_id=body.case_id)
