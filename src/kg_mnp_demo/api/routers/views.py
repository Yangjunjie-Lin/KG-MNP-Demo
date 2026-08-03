from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from kg_mnp_demo.api.dependencies import get_state
from kg_mnp_demo.api.schemas.assessment import WhatIfRequest
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.loader import project_root
from kg_mnp_demo.namespaces import CASE_JSON_FILES
from kg_mnp_demo.presentation import (
    AssessmentView,
    ComparisonView,
    DashboardView,
    OntologyView,
    TraceView,
)
import json

router = APIRouter(prefix="/views")


@router.get("/dashboard")
def dashboard():
    state = get_state()
    return DashboardView().build(ontology=state.ontology_service, repository=state.repository)


@router.get("/ontology")
def ontology_view():
    return OntologyView().build(get_state().ontology_service)


@router.get("/cases/{case_id}")
def case_view(case_id: str):
    json_name = CASE_JSON_FILES.get(case_id)
    payload = {"case_id": case_id}
    if json_name:
        path = project_root() / "inputs" / json_name
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
    latest = None
    try:
        latest = get_state().repository.get_latest_case_execution(case_id)
    except ApplicationError:
        latest = None
    from kg_mnp_demo.presentation import CaseView

    return CaseView().build(payload, latest)


@router.get("/assessments/{execution_id}")
def assessment_view(execution_id: str):
    record = get_state().repository.get_execution(execution_id)
    return AssessmentView().build(record)


@router.get("/assessments/{execution_id}/trace")
def assessment_trace_view(execution_id: str):
    record = get_state().repository.get_execution(execution_id)
    return TraceView().build(record.get("result") or {})


@router.get("/assessments/{execution_id}/timeline")
def assessment_timeline(execution_id: str):
    view = AssessmentView().build(get_state().repository.get_execution(execution_id))
    return {"execution_id": execution_id, "timeline": view["timeline"]}


@router.post("/what-if")
def what_if_view(body: dict[str, Any]):
    baseline = body.get("baseline_payload")
    changes = body.get("changes") or {}
    if not isinstance(baseline, dict):
        raise ApplicationError(
            ErrorCode.INPUT_SCHEMA_ERROR,
            details=["baseline_payload is required"],
        )
    result = get_state().assessment_service.run_what_if(baseline, changes)
    return ComparisonView().build(result)
