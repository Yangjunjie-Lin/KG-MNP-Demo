"""Explicit local-only Domain Pack discovery and exact-version lookup."""

from __future__ import annotations

from pathlib import Path

from zhigou_toolchain.contracts.errors import ContractError
from zhigou_toolchain.contracts.identifiers import normalize_identifier
from zhigou_toolchain.environment import get_setting

from .locking import verify_pack_lock
from .models import ResolvedDomainPack
from .validation import load_domain_pack_manifest, require_valid_domain_pack


class DomainPackRegistryError(ContractError):
    """The local registry is missing, ambiguous, or does not satisfy a request."""


def discover_domain_packs_root(explicit: Path | str | None = None) -> Path:
    """Resolve the documented root precedence and fail closed outside source dev."""

    candidate = explicit
    if candidate is None:
        configured = get_setting("DOMAIN_PACKS_ROOT")
        candidate = configured if configured else None
    if candidate is None:
        try:
            from zhigou_toolchain.paths import repository_root

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
        directories = [(directory, None) for directory in self.root.iterdir()]
        archive = self.root / ".versions"
        if archive.is_dir():
            from zhigou_toolchain._path_security import _is_link_like
            from zhigou_toolchain.contracts.identifiers import validate_semver
            if _is_link_like(archive):
                raise DomainPackRegistryError("Version archive must not be a filesystem link")
            for version_root in sorted(archive.iterdir()):
                if not version_root.is_dir() or _is_link_like(version_root):
                    raise DomainPackRegistryError("Invalid version archive directory")
                validate_semver(version_root.name)
                directories.extend((directory, version_root.name) for directory in version_root.iterdir())
        for directory, archived_version in sorted(directories, key=lambda item: str(item[0])):
            if not directory.is_dir() or not (directory / "pack.yaml").is_file():
                continue
            if archived_version is not None and (_is_link_like(directory) or not directory.resolve().is_relative_to(archive.resolve())):
                raise DomainPackRegistryError("Archived Pack must remain inside its version directory")
            manifest = load_domain_pack_manifest(directory)
            if archived_version is not None and manifest.pack_version != archived_version:
                raise DomainPackRegistryError("Archived Pack version differs from its directory")
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
