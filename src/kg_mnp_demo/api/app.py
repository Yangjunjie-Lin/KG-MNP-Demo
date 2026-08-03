"""KG-MNP FastAPI application."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from kg_mnp_demo.application.errors import ApplicationError

try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "API dependencies missing. Install with: pip install -e \".[api]\""
    ) from exc

from kg_mnp_demo.api.dependencies import AppState, get_state, set_state
from kg_mnp_demo.api.routers import (
    assessments,
    cases,
    competency_questions,
    examples,
    health,
    ontology,
    rules,
    views,
)


def _cors_origins() -> list[str]:
    raw = os.environ.get("KG_MNP_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    set_state(AppState())
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="KG-MNP Eligibility API",
        version="1.0.0",
        description="Frontend-ready backend for deterministic MNP eligibility assessment.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApplicationError)
    async def application_error_handler(_request: Request, exc: ApplicationError):
        status = 404 if exc.code.value.endswith("NOT_FOUND") else 400
        if exc.code.value == "INTERNAL_ERROR":
            status = 500
        return JSONResponse(status_code=status, content=exc.to_dict())

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception):
        err = ApplicationError(
            "INTERNAL_ERROR",
            message="内部错误。",
            details=[type(exc).__name__],
            retryable=True,
        )
        return JSONResponse(status_code=500, content=err.to_dict())

    api = "/api/v1"
    app.include_router(health.router, prefix=api, tags=["system"])
    app.include_router(assessments.router, prefix=api, tags=["assessments"])
    app.include_router(cases.router, prefix=api, tags=["cases"])
    app.include_router(ontology.router, prefix=api, tags=["ontology"])
    app.include_router(competency_questions.router, prefix=api, tags=["competency-questions"])
    app.include_router(rules.router, prefix=api, tags=["rules"])
    app.include_router(examples.router, prefix=api, tags=["examples"])
    app.include_router(views.router, prefix=api, tags=["views"])
    return app


app = create_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("KG_MNP_API_HOST", "127.0.0.1")
    port = int(os.environ.get("KG_MNP_API_PORT", "8000"))
    uvicorn.run("kg_mnp_demo.api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
