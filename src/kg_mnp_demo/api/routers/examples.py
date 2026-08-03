from __future__ import annotations

import json
import uuid

from fastapi import APIRouter

from kg_mnp_demo.api.dependencies import get_state
from kg_mnp_demo.application.assessment_service import write_assessment_artifacts
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.loader import project_root
from kg_mnp_demo.namespaces import CASE_FILES, CASE_JSON_FILES

router = APIRouter()


@router.get("/examples")
def list_examples():
    return {
        "items": [
            {"case_id": c, "json_file": CASE_JSON_FILES.get(c), "ttl_file": CASE_FILES[c]}
            for c in sorted(CASE_FILES)
        ]
    }


@router.get("/examples/{case_id}")
def get_example(case_id: str):
    if case_id not in CASE_FILES:
        raise ApplicationError(ErrorCode.CASE_NOT_FOUND, details=[case_id])
    json_name = CASE_JSON_FILES.get(case_id)
    payload = None
    if json_name and (project_root() / "inputs" / json_name).exists():
        payload = json.loads((project_root() / "inputs" / json_name).read_text(encoding="utf-8"))
    return {"case_id": case_id, "input": payload, "ttl_file": CASE_FILES[case_id]}


@router.post("/examples/{case_id}/run")
def run_example(case_id: str):
    state = get_state()
    example = get_example(case_id)
    if not example.get("input"):
        raise ApplicationError(
            ErrorCode.CASE_NOT_FOUND,
            message=f"案例无 JSON 输入：{case_id}",
            details=[case_id],
        )
    execution_id = str(uuid.uuid4())
    execution = state.assessment_service.assess_execution(
        example["input"], execution_id=execution_id
    )
    out = state.artifacts.execution_dir(execution_id)
    names = write_assessment_artifacts(execution, out, write_html=False)
    execution.response["artifacts"] = state.artifacts.relative_artifacts(names)
    state.repository.save_execution(
        execution_id=execution.response["execution_id"],
        case_id=execution.response["case_id"],
        assessment_time=execution.response["assessment_time"],
        input_payload=example["input"],
        result=execution.response,
        artifact_directory=out.name,
    )
    return execution.response
