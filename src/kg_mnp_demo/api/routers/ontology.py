from __future__ import annotations

from fastapi import APIRouter, Query

from kg_mnp_demo.api.dependencies import get_state
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode

router = APIRouter()


@router.get("/ontology/summary")
def ontology_summary():
    return get_state().ontology_service.get_summary()


@router.get("/ontology/modules")
def ontology_modules():
    return {"items": get_state().ontology_service.list_modules()}


@router.get("/ontology/classes")
def ontology_classes():
    return {"items": get_state().ontology_service.list_classes()}


@router.get("/ontology/classes/{name}")
def ontology_class_detail(name: str):
    detail = get_state().ontology_service.get_class_detail(name)
    if not detail:
        raise ApplicationError(ErrorCode.CASE_NOT_FOUND, message=f"未找到类：{name}", details=[name])
    return detail


@router.get("/ontology/properties")
def ontology_properties():
    svc = get_state().ontology_service
    return {
        "object_properties": svc.list_object_properties(),
        "data_properties": svc.list_data_properties(),
    }


@router.get("/ontology/graph")
def ontology_graph(module: str | None = Query(None)):
    return get_state().ontology_service.build_ontology_graph(module=module)
