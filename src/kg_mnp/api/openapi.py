from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kg_mnp import __version__
from kg_mnp.services.facade import ApplicationService


def build_openapi(service: ApplicationService) -> dict[str, Any]:
    from .app import create_app

    app = create_app(service)
    document = app.openapi()
    document["openapi"] = "3.1.0"
    document["info"]["x-toolchain-version"] = __version__
    document["info"]["x-api-version"] = "v1"
    document["info"]["x-semantic-compiler-policy"] = "resolved-from-package"
    return document


def export_openapi(service: ApplicationService, path: Path | str) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(build_openapi(service), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return destination
