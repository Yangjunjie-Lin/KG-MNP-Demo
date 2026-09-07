"""Service handles map to core workspaces; legacy records remain untrusted."""
from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from jsonschema import ValidationError

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.contracts.document_io import atomic_write_json, read_document
from kg_mnp.contracts.errors import ContractError
from kg_mnp.domain_packs.registry import DomainPackRegistry
from kg_mnp.lifecycle.registry.manifest import init_registry, load_manifest
from kg_mnp.workspace.locking import generate_project_lock
from kg_mnp.workspace.service import initialize_workspace, load_project_manifest
from kg_mnp.workspace.validation import validate_workspace

from .coordination import metadata_lock
from .errors import ServiceBoundaryError
from .models import PrincipalReference, ProjectHandle


def _catalog_path(root: Path) -> Path:
    return root / "service-projects.json"


def load_catalog(root: Path) -> dict:
    path = _catalog_path(root)
    if not path.exists():
        return {"projects": {}}
    try:
        value = read_document(path, max_bytes=32 * 1024 * 1024)
        if not isinstance(value, dict) or not isinstance(value.get("projects"), dict):
            raise TypeError("invalid catalog")
        return value
    except (OSError, ContractError, ValueError, TypeError) as exc:
        raise ServiceBoundaryError("PROJECT_CATALOG_INVALID", "project catalog is invalid", status_code=503) from exc


def save_catalog(root: Path, value: dict) -> None:
    atomic_write_json(_catalog_path(root), value)


def _safe_handle(root: Path, row: dict) -> ProjectHandle:
    try:
        handle = ProjectHandle(**row)
        candidate = Path(handle.root)
        base = (root / "projects").resolve()
        if candidate.is_symlink() or not candidate.resolve().is_relative_to(base):
            raise ValueError("outside project root")
        for parent in (candidate, *candidate.parents):
            if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
                raise ValueError("linked project root")
            if parent == root:
                break
        return handle
    except (TypeError, ValueError, OSError) as exc:
        raise ServiceBoundaryError("PROJECT_CATALOG_INVALID", "project mapping is invalid", status_code=503) from exc


def can_access(principal: PrincipalReference, project: ProjectHandle) -> bool:
    return principal.can("project:admin") or project.project_id in principal.project_ids or (
        not principal.project_ids and project.owner_id == principal.principal_id
    )


def require_access(principal: PrincipalReference, project: ProjectHandle) -> None:
    if not can_access(principal, project):
        raise ServiceBoundaryError("PROJECT_FORBIDDEN", "principal is not authorized for this project", status_code=403)


def inspect_project(handle: ProjectHandle, packs_root: str | None) -> ProjectHandle:
    if not handle.manifest_project_id or not handle.owner_id:
        return replace(handle, status="LEGACY_INCOMPLETE", migration_status="NEW_WORKSPACE_REQUIRED")
    result = validate_workspace(handle.root, domain_packs_root=packs_root)
    if result.valid:
        manifest = load_project_manifest(handle.root)
        packs = manifest.document["domain_packs"]
        mapping_valid = (
            manifest.project_id == handle.manifest_project_id
            and len(packs) == 1
            and packs[0]["pack_id"] == handle.domain_pack
            and packs[0]["pack_version"] == handle.domain_pack_version
        )
        try:
            mapping_valid = mapping_valid and load_manifest(handle.registry_root)["project_id"] == handle.project_id
        except (OSError, ValueError, ContractError):
            mapping_valid = False
        if not mapping_valid:
            return replace(handle, status="MAPPING_INVALID")
    return replace(handle, status=result.status)


def create_project(root: Path, name: str, principal: PrincipalReference, *,
                   domain_pack: str, domain_pack_version: str, packs_root: str | None = None) -> ProjectHandle:
    if not name.strip() or len(name) > 200 or any(char in name for char in "\\/:\x00"):
        raise ServiceBoundaryError("PROJECT_INVALID", "project name is invalid", status_code=422)
    from .packs import registry

    packs = registry(packs_root)
    if (domain_pack, domain_pack_version) not in packs.entries:
        raise ServiceBoundaryError("DOMAIN_PACK_VERSION_UNAVAILABLE", "exact Domain Pack version is unavailable", status_code=422)
    with metadata_lock(root / "service-data" / "projects-lock.sqlite3"):
        catalog = load_catalog(root)
        project_id = stable_urn("project", {"name": name, "owner": principal.principal_id})
        if project_id in catalog["projects"]:
            existing = inspect_project(_safe_handle(root, catalog["projects"][project_id]), packs_root)
            require_access(principal, existing)
            if (existing.domain_pack, existing.domain_pack_version, existing.status) != (domain_pack, domain_pack_version, "VALID"):
                raise ServiceBoundaryError("PROJECT_REBIND_FORBIDDEN", "existing workspace cannot be rebound or repaired implicitly", status_code=409)
            return existing
        suffix = project_id.rsplit(":", 1)[1]
        project_root = root / "projects" / suffix
        project_root.parent.mkdir(parents=True, exist_ok=True)
        core_id = "project-" + suffix
        try:
            initialize_workspace(project_root, project_id=core_id, project_version="0.1.0",
                                 display_name=name, domain_pack=domain_pack, domain_pack_version=domain_pack_version,
                                 domain_packs_root=packs_root)
            handle = ProjectHandle(project_id, name, str(project_root), "VALID", principal.principal_id,
                                   core_id, domain_pack, domain_pack_version)
            init_registry(handle.registry_root, project_id=project_id, created_by=principal.principal_id)
            checked = inspect_project(handle, packs_root)
            if checked.status != "VALID":
                raise ValueError("workspace validation failed")
        except (ContractError, ValidationError, OSError, ValueError) as exc:
            raise ServiceBoundaryError("WORKSPACE_CREATION_FAILED", "workspace initialization failed; inspect local diagnostics", status_code=422) from exc
        catalog["projects"][project_id] = asdict(handle)
        save_catalog(root, catalog)
        return handle


def get_project(root: Path, project_id: str) -> ProjectHandle:
    row = load_catalog(root).get("projects", {}).get(project_id)
    if not row:
        raise ServiceBoundaryError("PROJECT_NOT_FOUND", "project was not found", status_code=404)
    handle = _safe_handle(root, row)
    if handle.project_id != project_id:
        raise ServiceBoundaryError("PROJECT_CATALOG_INVALID", "project mapping is invalid", status_code=503)
    return handle


def list_projects(root: Path) -> list[ProjectHandle]:
    return [get_project(root, key) for key in sorted(load_catalog(root)["projects"])]


def lock_project(handle: ProjectHandle, packs_root: str | None) -> ProjectHandle:
    checked = inspect_project(handle, packs_root)
    if checked.status != "VALID":
        raise ServiceBoundaryError("PROJECT_REBIND_FORBIDDEN", "invalid/legacy workspace requires explicit recovery or a new workspace", status_code=409)
    generate_project_lock(load_project_manifest(handle.root), DomainPackRegistry(packs_root), check=True)
    return checked
