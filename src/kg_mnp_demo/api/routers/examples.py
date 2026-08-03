from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from kg_mnp_demo.api.dependencies import AppState, get_state
from kg_mnp_demo.api.schemas.assessment import AssessmentResponse
from kg_mnp_demo.api.schemas.common import ERROR_RESPONSES
from kg_mnp_demo.api.schemas.views import ExampleDetailResponse, ExampleListResponse
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.persist import persist_assessment
from kg_mnp_demo.loader import project_root
from kg_mnp_demo.namespaces import CASE_FILES, CASE_JSON_FILES, EXAMPLE_META

router = APIRouter()


def _example_item(case_id: str) -> dict:
    json_name = CASE_JSON_FILES.get(case_id)
    runnable = bool(json_name and (project_root() / "inputs" / json_name).exists())
    meta = EXAMPLE_META.get(case_id) or {}
    return {
        "case_id": case_id,
        "runnable": runnable,
        "input_format": "json" if runnable else "ttl",
        "expected_decision": meta.get("expected_decision"),
        "scenario": meta.get("scenario"),
        "json_file": json_name,
        "ttl_file": CASE_FILES.get(case_id),
    }


@router.get("/examples", response_model=ExampleListResponse, responses=ERROR_RESPONSES)
def list_examples():
    return {"items": [_example_item(c) for c in sorted(CASE_FILES)]}


@router.get(
    "/examples/{case_id}",
    response_model=ExampleDetailResponse,
    responses=ERROR_RESPONSES,
)
def get_example(case_id: str):
    if case_id not in CASE_FILES:
        raise ApplicationError(ErrorCode.EXAMPLE_NOT_FOUND, details=[case_id])
    item = _example_item(case_id)
    payload = None
    if item["json_file"]:
        path = project_root() / "inputs" / item["json_file"]
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
    return {**item, "input": payload}


@router.post(
    "/examples/{case_id}/run",
    response_model=AssessmentResponse,
    responses=ERROR_RESPONSES,
)
def run_example(case_id: str, state: AppState = Depends(get_state)):
    example = get_example(case_id)
    if not example.get("runnable") or not example.get("input"):
        raise ApplicationError(
            ErrorCode.EXAMPLE_NOT_FOUND,
            message=f"示例不可运行（缺少 JSON 输入）：{case_id}",
            details=[case_id],
        )
    return persist_assessment(
        payload=example["input"],
        repository=state.repository,
        artifacts=state.artifacts,
        assessment_service=state.assessment_service,
        persist=True,
        force_recompute=False,
    )
