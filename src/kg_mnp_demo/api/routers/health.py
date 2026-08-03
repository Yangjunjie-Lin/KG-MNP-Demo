from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from kg_mnp_demo.api.dependencies import get_state
from kg_mnp_demo.loader import project_root

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@router.get("/ready")
def ready():
    state = get_state()
    try:
        state.db.connection.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ready" if db_ok else "degraded",
        "sqlite": db_ok,
        "neo4j_required": False,
    }


@router.get("/meta")
def meta():
    return {
        "name": "kg-mnp-demo",
        "api_version": "v1",
        "project_root_name": project_root().name,
        "cors_note": "Configured via KG_MNP_CORS_ORIGINS",
        "backend": "rdf",
        "neo4j_required": False,
    }
