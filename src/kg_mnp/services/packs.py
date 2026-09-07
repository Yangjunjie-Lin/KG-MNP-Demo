"""Administrator-configured, local, exact-version Domain Pack discovery."""
from __future__ import annotations

from jsonschema import ValidationError

from kg_mnp.contracts.errors import ContractError
from kg_mnp.domain_packs.registry import DomainPackRegistry
from kg_mnp.domain_packs.validation import load_domain_pack_manifest

from .errors import ServiceBoundaryError


def registry(root: str | None) -> DomainPackRegistry:
    try:
        result = DomainPackRegistry(root)
        for child in result.root.iterdir():
            if child.is_symlink() or (hasattr(child, "is_junction") and child.is_junction()):
                raise ValueError("linked pack entry")
        for path in result.entries.values():
            if not path.is_relative_to(result.root):
                raise ValueError("pack outside configured root")
        return result
    except (OSError, ContractError, ValueError, ValidationError) as exc:
        raise ServiceBoundaryError("DOMAIN_PACK_DISCOVERY_FAILED", "configured Domain Pack root cannot be resolved or parsed", status_code=503) from exc


def discover(root: str | None) -> dict:
    packs = registry(root)
    rows = []
    for pack_id, version, path in packs.list():
        manifest = load_domain_pack_manifest(path).document
        row = {"pack_id": pack_id, "pack_version": version, "lifecycle": manifest["lifecycle"],
               "capabilities": manifest["capabilities"], "lock_status": "UNVERIFIED",
               "availability": "UNAVAILABLE", "content_digest": None}
        try:
            resolved = packs.resolve(pack_id, version)
            row.update(lock_status="VERIFIED", content_digest=resolved.lock.content_digest,
                       availability="UNAVAILABLE" if manifest["lifecycle"] == "PLANNED" else "AVAILABLE")
        except (ContractError, ValueError, OSError, ValidationError):
            row["lock_status"] = "INVALID"
        rows.append(row)
    return {"domain_packs": rows}
