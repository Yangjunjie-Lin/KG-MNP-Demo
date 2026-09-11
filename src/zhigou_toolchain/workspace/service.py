"""Transactional Project Workspace initialization and opening."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from zhigou_toolchain.contracts.document_io import atomic_write_bytes, read_document
from zhigou_toolchain.contracts.errors import ContractError, PathSecurityError
from zhigou_toolchain.contracts.identifiers import normalize_identifier, validate_semver
from zhigou_toolchain.contracts.registry import validate_contract
from zhigou_toolchain.domain_packs.registry import DomainPackRegistry

from .layout import WORKSPACE_LAYOUT_VERSION, create_layout
from .locking import generate_project_lock, load_project_lock
from .models import ProjectManifest, ProjectWorkspace


class WorkspaceError(ContractError):
    """A Project Workspace cannot be initialized or opened safely."""


def load_project_manifest(workspace_root: Path | str) -> ProjectManifest:
    root = Path(workspace_root).resolve(strict=True)
    path = root / "project.yaml"
    if not path.is_file():
        raise WorkspaceError("Project manifest is missing")
    value = read_document(path)
    if not isinstance(value, dict):
        raise WorkspaceError("Project manifest root must be an object")
    validate_contract("project-manifest", value)
    _validate_project_semantics(value)
    return ProjectManifest(document=value, path=path)


def _validate_project_semantics(value: dict[str, Any]) -> None:
    packs = value["domain_packs"]
    keys = [(item["pack_id"], item["pack_version"]) for item in packs]
    if keys != sorted(keys):
        raise WorkspaceError("Project domain_packs must be sorted")
    if len(keys) != len(set(keys)):
        raise WorkspaceError("Project domain_packs must be unique")
    pack_ids = {item["pack_id"] for item in packs}
    if value["primary_domain_pack"] not in pack_ids:
        raise WorkspaceError("primary_domain_pack must reference a declared pack")
    for profile_name, profile in value["profiles"].items():
        if profile["pack_id"] not in pack_ids:
            raise WorkspaceError(f"profile {profile_name} references an undeclared pack")
        if profile["entrypoints"] != sorted(profile["entrypoints"]):
            raise WorkspaceError(f"profile {profile_name} entrypoints must be sorted")


def _manifest_bytes(value: dict[str, Any]) -> bytes:
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        sort_keys=False,
        width=100,
    ).encode("utf-8")


def initialize_workspace(
    workspace_path: Path | str,
    *,
    project_id: str,
    project_version: str,
    display_name: str,
    domain_pack: str,
    domain_pack_version: str,
    domain_packs_root: Path | str | None = None,
) -> ProjectWorkspace:
    """Build a complete workspace in a sibling staging directory then rename it."""

    normalize_identifier(project_id, label="project_id")
    validate_semver(project_version)
    normalize_identifier(domain_pack, label="pack_id")
    validate_semver(domain_pack_version)
    if not isinstance(display_name, str) or not display_name.strip():
        raise WorkspaceError("display_name must be non-empty")
    target = Path(workspace_path).expanduser().absolute()
    parent = target.parent.resolve(strict=True)
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise PathSecurityError("Workspace target must be a real directory")
        if any(target.iterdir()):
            raise WorkspaceError("Workspace initialization refuses a non-empty directory")
    registry = DomainPackRegistry(domain_packs_root)
    resolved = registry.resolve(domain_pack, domain_pack_version)
    entrypoints = sorted(resolved.manifest.document["entrypoints"])
    manifest_value: dict[str, Any] = {
        "manifest_kind": "KG_MNP_PROJECT",
        "schema_version": "1.0.0",
        "project_id": project_id,
        "project_version": project_version,
        "display_name": display_name.strip(),
        "description": f"Project Workspace bound to {domain_pack} {domain_pack_version}.",
        "workspace_layout_version": WORKSPACE_LAYOUT_VERSION,
        "domain_packs": [
            {
                "pack_id": domain_pack,
                "pack_version": domain_pack_version,
                "required_capabilities": sorted(resolved.manifest.capabilities),
                "selected_entrypoints": entrypoints,
            }
        ],
        "primary_domain_pack": domain_pack,
        "profiles": {
            "default": {"pack_id": domain_pack, "entrypoints": entrypoints}
        },
        "settings": {"offline_only": True, "strict_validation": True},
        "extensions": {},
    }
    validate_contract("project-manifest", manifest_value)
    _validate_project_semantics(manifest_value)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.kg-mnp-init-", dir=parent))
    try:
        create_layout(staging)
        manifest_path = staging / "project.yaml"
        atomic_write_bytes(manifest_path, _manifest_bytes(manifest_value))
        manifest = ProjectManifest(document=manifest_value, path=manifest_path)
        lock = generate_project_lock(manifest, registry)
        if target.exists():
            target.rmdir()
        os.replace(staging, target)
        final_manifest = ProjectManifest(document=manifest_value, path=target / "project.yaml")
        final_lock = type(lock)(document=lock.document, path=target / "project.lock.json")
        return ProjectWorkspace(root=target, manifest=final_manifest, lock=final_lock)
    except BaseException:
        resolved_staging = staging.resolve(strict=False)
        if resolved_staging.parent == parent and resolved_staging.name.startswith(
            f".{target.name}.kg-mnp-init-"
        ):
            shutil.rmtree(resolved_staging, ignore_errors=True)
        raise


def open_workspace(workspace_path: Path | str) -> ProjectWorkspace:
    root = Path(workspace_path).resolve(strict=True)
    manifest = load_project_manifest(root)
    lock = load_project_lock(root)
    return ProjectWorkspace(root=root, manifest=manifest, lock=lock)

