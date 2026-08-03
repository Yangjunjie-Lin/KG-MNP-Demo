"""Every public /api/v1 route should declare a response_model (OpenAPI schema)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from kg_mnp_demo.api.app import create_app

IGNORE_PATHS = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}


def test_all_public_routes_have_response_schema():
    app = create_app()
    missing = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        if not path.startswith("/api/v1"):
            continue
        if path in IGNORE_PATHS:
            continue
        if not methods or methods == {"HEAD"}:
            continue
        response_model = getattr(route, "response_model", None)
        if response_model is None:
            missing.append(f"{sorted(methods)} {path}")
    assert missing == [], f"routes missing response_model: {missing}"
