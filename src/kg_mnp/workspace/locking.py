"""Deterministic ProjectLock construction and verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kg_mnp.contracts.canonical import (
    CANONICAL_JSON_PROFILE,
    canonical_lock_preimage,
    file_sha256,
    semantic_hash,
)
from kg_mnp.contracts.catalog import ContractCatalog, verify_catalog_lock
from kg_mnp.contracts.document_io import atomic_write_json, read_document
from kg_mnp.contracts.errors import ContractError
from kg_mnp.contracts.identifiers import project_lock_urn
from kg_mnp.contracts.registry import validate_contract
from kg_mnp.domain_packs.registry import DomainPackRegistry
from kg_mnp.domain_packs.resolver import resolve_dependency_closure

from .models import ProjectLock, ProjectManifest


class ProjectLockError(ContractError):
    """A Project Lock is absent, stale, or tampered."""


def build_project_lock(
    manifest: ProjectManifest,
    registry: DomainPackRegistry,
) -> dict[str, Any]:
    verify_catalog_lock()
    roots = tuple(
        (item["pack_id"], item["pack_version"])
        for item in manifest.document["domain_packs"]
    )
    closure = resolve_dependency_closure(registry, roots)
    declarations = {
        (item["pack_id"], item["pack_version"]): item
        for item in manifest.document["domain_packs"]
    }
    for pack in closure:
        declaration = declarations.get((pack.manifest.pack_id, pack.manifest.pack_version))
        if declaration is None:
            continue
        missing = sorted(set(declaration["required_capabilities"]) - set(pack.manifest.capabilities))
        if missing:
            raise ProjectLockError(
                f"Project requires missing capabilities from {pack.manifest.pack_id}: {', '.join(missing)}"
            )
        selected = declaration.get("selected_entrypoints", [])
        unknown = sorted(set(selected) - set(pack.manifest.document["entrypoints"]))
        if unknown:
            raise ProjectLockError(
                f"Project selects unknown entrypoints from {pack.manifest.pack_id}: {', '.join(unknown)}"
            )
    resolved = [
        {
            "pack_id": item.manifest.pack_id,
            "pack_version": item.manifest.pack_version,
            "pack_lock_id": item.lock.lock_id,
            "pack_content_digest": item.lock.content_digest,
            "dependency_depth": item.dependency_depth,
            "capabilities": sorted(item.manifest.capabilities),
        }
        for item in closure
    ]
    resolved.sort(key=lambda item: (item["pack_id"], item["pack_version"]))
    catalog = ContractCatalog.load()
    core: dict[str, Any] = {
        "manifest_kind": "KG_MNP_PROJECT_LOCK",
        "schema_version": "1.0.0",
        "project_id": manifest.project_id,
        "project_version": manifest.project_version,
        "project_manifest_file_sha256": file_sha256(manifest.path),
        "project_manifest_semantic_sha256": semantic_hash(manifest.document),
        "contract_catalog_digest": catalog.digest,
        "resolved_domain_packs": resolved,
        "workspace_layout_version": manifest.document["workspace_layout_version"],
        "canonicalization_profile": CANONICAL_JSON_PROFILE,
    }
    content_digest = semantic_hash(core)
    lock = {
        **core,
        "content_digest": content_digest,
        "lock_id": project_lock_urn({"content_digest": content_digest}),
    }
    validate_contract("project-lock", lock)
    return lock


def generate_project_lock(
    manifest: ProjectManifest,
    registry: DomainPackRegistry,
    *,
    check: bool = False,
) -> ProjectLock:
    expected = build_project_lock(manifest, registry)
    path = manifest.path.parent / "project.lock.json"
    if check:
        if not path.is_file() or read_document(path) != expected:
            raise ProjectLockError("Project Lock is stale")
    else:
        atomic_write_json(path, expected)
    return ProjectLock(document=expected, path=path)


def load_project_lock(workspace_root: Path) -> ProjectLock:
    path = workspace_root / "project.lock.json"
    if not path.is_file():
        raise ProjectLockError("Project Lock is missing")
    value = read_document(path)
    if not isinstance(value, dict):
        raise ProjectLockError("Project Lock root must be an object")
    validate_contract("project-lock", value)
    return ProjectLock(document=value, path=path)


def verify_project_lock(
    manifest: ProjectManifest,
    registry: DomainPackRegistry,
) -> ProjectLock:
    actual = load_project_lock(manifest.path.parent)
    expected = build_project_lock(manifest, registry)
    if actual.document != expected:
        raise ProjectLockError("Project Lock mismatch")
    preimage = canonical_lock_preimage(actual.document, "content_digest", "lock_id")
    if semantic_hash(preimage) != actual.document["content_digest"]:
        raise ProjectLockError("Project Lock content digest mismatch")
    return actual

