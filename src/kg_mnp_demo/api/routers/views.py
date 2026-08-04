from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends

from kg_mnp_demo.api.dependencies import AppState, get_state
from kg_mnp_demo.api.schemas.assessment import WhatIfResponse, WhatIfViewRequest
from kg_mnp_demo.api.schemas.common import ERROR_RESPONSES
from kg_mnp_demo.api.schemas.views import (
    AssessmentViewResponse,
    CaseListViewResponse,
    CaseViewResponse,
    DashboardViewResponse,
    OntologyViewResponse,
    TimelineResponse,
    TraceViewResponse,
)
from kg_mnp_demo.application.errors import ApplicationError
from kg_mnp_demo.loader import project_root
from kg_mnp_demo.namespaces import CASE_JSON_FILES
from kg_mnp_demo.presentation import (
    AssessmentView,
    CaseCatalogView,
    CaseView,
    ComparisonView,
    DashboardView,
    OntologyView,
    TraceView,
)

router = APIRouter(prefix="/views")


@router.get(
    "/dashboard",
    response_model=DashboardViewResponse,
    responses=ERROR_RESPONSES,
)
def dashboard(state: AppState = Depends(get_state)):
    return DashboardView().build(
        ontology=state.ontology_service, repository=state.repository
    )


@router.get(
    "/ontology",
    response_model=OntologyViewResponse,
    responses=ERROR_RESPONSES,
)
def ontology_view(state: AppState = Depends(get_state)):
    return OntologyView().build(state.ontology_service)


@router.get(
    "/cases",
    response_model=CaseListViewResponse,
    responses=ERROR_RESPONSES,
)
def case_catalog_view(state: AppState = Depends(get_state)):
    """Return the complete case catalog and latest execution summaries.

    The view is intentionally separate from ``/cases``: callers that need a
    full history can continue using the case-history endpoint, while list
    pages can obtain every row with one request.
    """
    return CaseCatalogView().build(state.repository)


@router.get(
    "/cases/{case_id}",
    response_model=CaseViewResponse,
    responses=ERROR_RESPONSES,
)
def case_view(case_id: str, state: AppState = Depends(get_state)):
    json_name = CASE_JSON_FILES.get(case_id)
    payload: dict[str, Any] = {"case_id": case_id}
    if json_name:
        path = project_root() / "inputs" / json_name
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
    latest = None
    try:
        latest = state.repository.get_latest_case_execution(case_id)
    except ApplicationError:
        latest = None
    return CaseView().build(payload, latest)


@router.get(
    "/assessments/{execution_id}",
    response_model=AssessmentViewResponse,
    responses=ERROR_RESPONSES,
)
def assessment_view(execution_id: str, state: AppState = Depends(get_state)):
    record = state.repository.get_execution(execution_id)
    return AssessmentView().build(record)


@router.get(
    "/assessments/{execution_id}/trace",
    response_model=TraceViewResponse,
    responses=ERROR_RESPONSES,
)
def assessment_trace_view(execution_id: str, state: AppState = Depends(get_state)):
    record = state.repository.get_execution(execution_id)
    return TraceView().build(record.get("result") or {})


@router.get(
    "/assessments/{execution_id}/timeline",
    response_model=TimelineResponse,
    responses=ERROR_RESPONSES,
)
def assessment_timeline(execution_id: str, state: AppState = Depends(get_state)):
    view = AssessmentView().build(state.repository.get_execution(execution_id))
    return {"execution_id": execution_id, "timeline": view["timeline"]}


@router.post(
    "/what-if",
    response_model=WhatIfResponse,
    responses=ERROR_RESPONSES,
)
def what_if_view(body: WhatIfViewRequest, state: AppState = Depends(get_state)):
    baseline = body.baseline_payload.to_pipeline_dict()
    result = state.assessment_service.run_what_if(baseline, body.changes)
    return ComparisonView().build(result)
