from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from kg_mnp_demo.api.dependencies import AppState, get_state
from kg_mnp_demo.api.schemas.common import ERROR_RESPONSES
from kg_mnp_demo.api.schemas.ontology import (
    OntologyClassListResponse,
    OntologyClassResponse,
    OntologyGraphResponse,
    OntologyModuleListResponse,
    OntologyPropertiesResponse,
    OntologySummaryResponse,
)
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode

router = APIRouter()


@router.get(
    "/ontology/summary",
    response_model=OntologySummaryResponse,
    responses=ERROR_RESPONSES,
)
def ontology_summary(state: AppState = Depends(get_state)):
    return state.ontology_service.get_summary()


@router.get(
    "/ontology/modules",
    response_model=OntologyModuleListResponse,
    responses=ERROR_RESPONSES,
)
def ontology_modules(state: AppState = Depends(get_state)):
    return {"items": state.ontology_service.list_modules()}


@router.get(
    "/ontology/classes",
    response_model=OntologyClassListResponse,
    responses=ERROR_RESPONSES,
)
def ontology_classes(state: AppState = Depends(get_state)):
    return {"items": state.ontology_service.list_classes()}


@router.get(
    "/ontology/classes/{name}",
    response_model=OntologyClassResponse,
    responses=ERROR_RESPONSES,
)
def ontology_class_detail(name: str, state: AppState = Depends(get_state)):
    detail = state.ontology_service.get_class_detail(name)
    if not detail:
        raise ApplicationError(
            ErrorCode.ONTOLOGY_TERM_NOT_FOUND,
            message=f"未找到类：{name}",
            details=[name],
        )
    return detail


@router.get(
    "/ontology/properties",
    response_model=OntologyPropertiesResponse,
    responses=ERROR_RESPONSES,
)
def ontology_properties(state: AppState = Depends(get_state)):
    svc = state.ontology_service
    return {
        "object_properties": svc.list_object_properties(),
        "data_properties": svc.list_data_properties(),
    }


@router.get(
    "/ontology/graph",
    response_model=OntologyGraphResponse,
    responses=ERROR_RESPONSES,
)
def ontology_graph(
    module: str | None = Query(None),
    state: AppState = Depends(get_state),
):
    return state.ontology_service.build_ontology_graph(module=module)
