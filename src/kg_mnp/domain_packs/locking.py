"""Deterministic DomainPackLock generation and verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kg_mnp.contracts.canonical import (
    CANONICAL_JSON_PROFILE,
    canonical_lock_preimage,
    file_sha256,
    semantic_hash,
)
from kg_mnp.contracts.document_io import atomic_write_json, read_document
from kg_mnp.contracts.errors import ContractError
from kg_mnp.contracts.identifiers import pack_lock_urn
from kg_mnp.contracts.registry import validate_contract

from .models import DomainPackLock, DomainPackManifest
from .security import asset_path


class DomainPackLockError(ContractError):
    """A Domain Pack lock is missing, stale, or tampered."""


def build_pack_lock(manifest: DomainPackManifest) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    for asset in sorted(manifest.document["assets"], key=lambda item: item["asset_id"]):
        path = asset_path(manifest.path.parent, asset["path"])
        assets.append(
            {
                "asset_id": asset["asset_id"],
                "path": asset["path"],
                "media_type": asset["media_type"],
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    dependencies = sorted(
        manifest.document["dependencies"],
        key=lambda item: (item["pack_id"], item["pack_version"]),
    )
    core: dict[str, Any] = {
        "manifest_kind": "KG_MNP_DOMAIN_PACK_LOCK",
        "schema_version": "1.0.0",
        "pack_id": manifest.pack_id,
        "pack_version": manifest.pack_version,
        "manifest_file_sha256": file_sha256(manifest.path),
        "manifest_semantic_sha256": semantic_hash(manifest.document),
        "assets": assets,
        "dependencies": dependencies,
        "canonicalization_profile": CANONICAL_JSON_PROFILE,
    }
    content_digest = semantic_hash(core)
    lock = {
        **core,
        "content_digest": content_digest,
        "lock_id": pack_lock_urn({"content_digest": content_digest}),
    }
    validate_contract("domain-pack-lock", lock)
    return lock


def generate_pack_lock(manifest: DomainPackManifest, *, check: bool = False) -> DomainPackLock:
    expected = build_pack_lock(manifest)
    path = manifest.path.parent / "pack.lock.json"
    if check:
        if not path.is_file() or read_document(path) != expected:
            raise DomainPackLockError(f"stale Domain Pack lock: {manifest.pack_id}")
    else:
        atomic_write_json(path, expected)
    return DomainPackLock(document=expected, path=path)


def load_pack_lock(pack_root: Path) -> DomainPackLock:
    path = pack_root / "pack.lock.json"
    if not path.is_file():
        raise DomainPackLockError(f"missing Domain Pack lock: {pack_root.name}")
    value = read_document(path)
    if not isinstance(value, dict):
        raise DomainPackLockError("Domain Pack lock root must be an object")
    validate_contract("domain-pack-lock", value)
    return DomainPackLock(document=value, path=path)


def verify_pack_lock(manifest: DomainPackManifest) -> DomainPackLock:
    actual = load_pack_lock(manifest.path.parent)
    expected = build_pack_lock(manifest)
    if actual.document != expected:
        raise DomainPackLockError(f"Domain Pack lock mismatch: {manifest.pack_id}")
    preimage = canonical_lock_preimage(actual.document, "content_digest", "lock_id")
    if semantic_hash(preimage) != actual.content_digest:
        raise DomainPackLockError(f"Domain Pack content digest mismatch: {manifest.pack_id}")
    return actual

