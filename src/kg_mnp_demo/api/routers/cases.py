from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from kg_mnp_demo.api.dependencies import AppState, get_state
from kg_mnp_demo.api.schemas.assessment import AssessmentRecordResponse
from kg_mnp_demo.api.schemas.common import (
    ERROR_RESPONSES,
    CaseDetailResponse,
    CaseHistoryResponse,
    CaseListResponse,
)
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.loader import project_root
from kg_mnp_demo.namespaces import CASE_FILES, CASE_JSON_FILES, EXAMPLE_META

router = APIRouter()


@router.get("/cases", response_model=CaseListResponse, responses=ERROR_RESPONSES)
def list_cases():
    items = []
    for case_id in sorted(CASE_FILES):
        meta = EXAMPLE_META.get(case_id) or {}
        items.append(
            {
                "case_id": case_id,
                "ttl_file": CASE_FILES[case_id],
                "json_file": CASE_JSON_FILES.get(case_id),
                "expected_decision": meta.get("expected_decision"),
                "scenario": meta.get("scenario"),
            }
        )
    return {"items": items}


@router.get(
    "/cases/{case_id}",
    response_model=CaseDetailResponse,
    responses=ERROR_RESPONSES,
)
def get_case(case_id: str):
    if case_id not in CASE_FILES:
        raise ApplicationError(ErrorCode.CASE_NOT_FOUND, details=[case_id])
    json_name = CASE_JSON_FILES.get(case_id)
    payload = None
    if json_name:
        path = project_root() / "inputs" / json_name
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
    meta = EXAMPLE_META.get(case_id) or {}
    return {
        "case_id": case_id,
        "ttl_file": CASE_FILES[case_id],
        "json_file": json_name,
        "input": payload,
        "expected_decision": meta.get("expected_decision"),
        "scenario": meta.get("scenario"),
    }


@router.get(
    "/cases/{case_id}/history",
    response_model=CaseHistoryResponse,
    responses=ERROR_RESPONSES,
)
def case_history(case_id: str, state: AppState = Depends(get_state)):
    return {"case_id": case_id, "items": state.repository.list_case_history(case_id)}


@router.get(
    "/cases/{case_id}/latest",
    response_model=AssessmentRecordResponse | None,
    responses=ERROR_RESPONSES,
)
def case_latest(case_id: str, state: AppState = Depends(get_state)):
    """Latest execution record for a case, or null when history is empty."""
    return state.repository.get_latest_case_execution(case_id)
