from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from kg_mnp_demo.api.dependencies import AppState, get_state
from kg_mnp_demo.api.schemas.common import (
    ERROR_RESPONSES,
    HealthResponse,
    MetaResponse,
    ReadyResponse,
)
from kg_mnp_demo.loader import project_root

router = APIRouter()


@router.get("/health", response_model=HealthResponse, responses=ERROR_RESPONSES)
def health():
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@router.get("/ready", response_model=ReadyResponse, responses=ERROR_RESPONSES)
def ready(state: AppState = Depends(get_state)):
    try:
        state.db.fetchone("SELECT 1")
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ready" if db_ok else "degraded",
        "sqlite": db_ok,
        "neo4j_required": False,
    }


@router.get("/meta", response_model=MetaResponse, responses=ERROR_RESPONSES)
def meta():
    return {
        "name": "kg-mnp-demo",
        "api_version": "v1",
        "schema_version": "1.0",
        "project_root_name": project_root().name,
        "cors_note": "Configured via KG_MNP_CORS_ORIGINS",
        "max_request_bytes_env": "KG_MNP_MAX_REQUEST_BYTES",
        "backend": "rdf",
        "neo4j_required": False,
    }
