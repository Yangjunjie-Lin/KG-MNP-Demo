from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends

from kg_mnp_demo.api.dependencies import AppState, get_state
from kg_mnp_demo.api.schemas.assessment import AssessmentResponse
from kg_mnp_demo.api.schemas.common import ERROR_RESPONSES
from kg_mnp_demo.api.schemas.views import ExampleDetailResponse, ExampleListResponse
from kg_mnp_demo.application.assessment_service import write_assessment_artifacts
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.serializers import to_iso_utc
from kg_mnp_demo.input_adapter import normalize_case_input
from kg_mnp_demo.loader import project_root
from kg_mnp_demo.namespaces import CASE_FILES, CASE_JSON_FILES, EXAMPLE_META
from kg_mnp_demo.storage import compute_input_hash

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
    payload = example["input"]
    normalized = normalize_case_input(payload)
    assessment_time = to_iso_utc(normalized.assessment_time) or ""
    input_hash = compute_input_hash(payload)
    existing = state.repository.find_idempotent_execution(
        normalized.case_id, assessment_time, input_hash
    )
    if existing:
        return existing.get("result") or existing

    execution_id = str(uuid.uuid4())
    execution = state.assessment_service.assess_execution(
        payload, execution_id=execution_id
    )
    out = state.artifacts.execution_dir(execution_id)
    wrote = False
    try:
        names = write_assessment_artifacts(execution, out, write_html=False)
        execution.response["artifacts"] = state.artifacts.relative_artifacts(names)
        wrote = True
        record = state.repository.save_execution(
            execution_id=execution.response["execution_id"],
            case_id=execution.response["case_id"],
            assessment_time=execution.response["assessment_time"],
            input_payload=payload,
            result=execution.response,
            artifact_directory=out.name,
        )
        if record.get("execution_id") != execution_id:
            state.artifacts.cleanup_execution_dir(execution_id)
        return record.get("result") or execution.response
    except Exception:
        if wrote:
            state.artifacts.cleanup_execution_dir(execution_id)
        raise
