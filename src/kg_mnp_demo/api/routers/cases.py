from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from kg_mnp_demo.api.dependencies import get_state
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.loader import project_root
from kg_mnp_demo.namespaces import CASE_FILES, CASE_JSON_FILES

router = APIRouter()


@router.get("/cases")
def list_cases():
    items = []
    for case_id in sorted(CASE_FILES):
        items.append(
            {
                "case_id": case_id,
                "ttl_file": CASE_FILES[case_id],
                "json_file": CASE_JSON_FILES.get(case_id),
            }
        )
    return {"items": items}


@router.get("/cases/{case_id}")
def get_case(case_id: str):
    if case_id not in CASE_FILES:
        raise ApplicationError(ErrorCode.CASE_NOT_FOUND, details=[case_id])
    json_name = CASE_JSON_FILES.get(case_id)
    payload = None
    if json_name:
        path = project_root() / "inputs" / json_name
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "case_id": case_id,
        "ttl_file": CASE_FILES[case_id],
        "json_file": json_name,
        "input": payload,
    }


@router.get("/cases/{case_id}/history")
def case_history(case_id: str):
    return {"case_id": case_id, "items": get_state().repository.list_case_history(case_id)}


@router.get("/cases/{case_id}/latest")
def case_latest(case_id: str):
    return get_state().repository.get_latest_case_execution(case_id)
