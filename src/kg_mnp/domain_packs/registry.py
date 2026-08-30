"""Explicit local-only Domain Pack discovery and exact-version lookup."""

from __future__ import annotations

import os
from pathlib import Path

from kg_mnp.contracts.errors import ContractError
from kg_mnp.contracts.identifiers import normalize_identifier

from .locking import verify_pack_lock
from .models import ResolvedDomainPack
from .validation import load_domain_pack_manifest, require_valid_domain_pack


class DomainPackRegistryError(ContractError):
    """The local registry is missing, ambiguous, or does not satisfy a request."""


def discover_domain_packs_root(explicit: Path | str | None = None) -> Path:
    """Resolve the documented root precedence and fail closed outside source dev."""

    candidate = explicit
    if candidate is None:
        configured = os.environ.get("KG_MNP_DOMAIN_PACKS_ROOT")
        candidate = configured if configured else None
    if candidate is None:
        try:
            from kg_mnp.paths import repository_root

            development_root = repository_root() / "domain_packs"
        except RuntimeError as exc:
            raise DomainPackRegistryError(
                "Domain Pack root is not configured outside a source checkout"
            ) from exc
        candidate = development_root
    root = Path(candidate).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise DomainPackRegistryError(f"Domain Pack root is not a directory: {root.name}")
    return root


class DomainPackRegistry:
    """A deterministic index over direct child packs of an explicit root."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = discover_domain_packs_root(root)
        self._entries: dict[tuple[str, str], Path] | None = None

    def _scan(self) -> dict[tuple[str, str], Path]:
        entries: dict[tuple[str, str], Path] = {}
        for directory in sorted(self.root.iterdir(), key=lambda item: item.name):
            if not directory.is_dir() or not (directory / "pack.yaml").is_file():
                continue
            manifest = load_domain_pack_manifest(directory)
            key = (manifest.pack_id, manifest.pack_version)
            if key in entries:
                raise DomainPackRegistryError(
                    f"duplicate Domain Pack id/version: {key[0]} {key[1]}"
                )
            entries[key] = directory.resolve(strict=True)
        return entries

    @property
    def entries(self) -> dict[tuple[str, str], Path]:
        if self._entries is None:
            self._entries = self._scan()
        return dict(self._entries)

    def list(self) -> tuple[tuple[str, str, Path], ...]:
        return tuple(
            (pack_id, version, path)
            for (pack_id, version), path in sorted(self.entries.items())
        )

    def resolve(self, pack_id: str, pack_version: str) -> ResolvedDomainPack:
        normalize_identifier(pack_id, label="pack_id")
        path = self.entries.get((pack_id, pack_version))
        if path is None:
            raise DomainPackRegistryError(
                f"local Domain Pack not found: {pack_id} {pack_version}"
            )
        manifest = require_valid_domain_pack(path, verify_lock=False)
        lock = verify_pack_lock(manifest)
        return ResolvedDomainPack(root=path, manifest=manifest, lock=lock)

    def resolve_path_or_id(
        self,
        value: Path | str,
        *,
        pack_version: str | None = None,
    ) -> Path:
        candidate = Path(value)
        if candidate.exists():
            return candidate.resolve(strict=True)
        pack_id = normalize_identifier(str(value), label="pack_id")
        matches = [
            (version, path)
            for (found_id, version), path in self.entries.items()
            if found_id == pack_id and (pack_version is None or version == pack_version)
        ]
        if len(matches) != 1:
            raise DomainPackRegistryError(
                f"Domain Pack id is missing or ambiguous: {pack_id}"
            )
        return matches[0][1]
