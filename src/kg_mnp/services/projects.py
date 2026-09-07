from __future__ import annotations

import json
from pathlib import Path

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.lifecycle.registry.manifest import init_registry

from .errors import ServiceBoundaryError
from .models import PrincipalReference, ProjectHandle


def _catalog_path(root: Path) -> Path:
    return root / "service-projects.json"


def load_catalog(root: Path) -> dict:
    path = _catalog_path(root)
    if not path.is_file():
        return {"projects": {}}
    try:
        return json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise ServiceBoundaryError("PROJECT_CATALOG_INVALID", "project catalog is invalid", status_code=503) from exc


def save_catalog(root: Path, value: dict) -> None:
    _catalog_path(root).write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def create_project(root: Path, name: str, principal: PrincipalReference) -> ProjectHandle:
    if not name or any(char in name for char in "\\/:\x00"):
        raise ServiceBoundaryError("PROJECT_INVALID", "project name is invalid", status_code=422)
    catalog = load_catalog(root)
    project_id = stable_urn("project", {"name": name, "owner": principal.principal_id})
    if project_id in catalog["projects"]:
        return ProjectHandle(**catalog["projects"][project_id])
    project_root = root / "projects" / project_id.rsplit(":", 1)[1]
    project_root.mkdir(parents=True, exist_ok=True)
    init_registry(project_root, project_id=project_id, registry_name="local")
    handle = ProjectHandle(project_id, name, str(project_root), "OPEN")
    catalog["projects"][project_id] = handle.__dict__
    save_catalog(root, catalog)
    return handle


def get_project(root: Path, project_id: str) -> ProjectHandle:
    row = load_catalog(root).get("projects", {}).get(project_id)
    if not row:
        raise ServiceBoundaryError("PROJECT_NOT_FOUND", "project was not found", status_code=404)
    return ProjectHandle(**row)


def list_projects(root: Path) -> list[ProjectHandle]:
    return [ProjectHandle(**row) for row in load_catalog(root).get("projects", {}).values()]
