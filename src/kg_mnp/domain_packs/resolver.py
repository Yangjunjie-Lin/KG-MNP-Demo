"""Exact local Domain Pack dependency closure resolution."""

from __future__ import annotations

from dataclasses import replace

from .models import ResolvedDomainPack
from .registry import DomainPackRegistry, DomainPackRegistryError


def resolve_dependency_closure(
    registry: DomainPackRegistry,
    roots: tuple[tuple[str, str], ...],
) -> tuple[ResolvedDomainPack, ...]:
    """Resolve, verify and topologically depth-label an exact local closure."""

    selected: dict[str, str] = {}
    resolved: dict[tuple[str, str], ResolvedDomainPack] = {}
    depths: dict[tuple[str, str], int] = {}
    active: list[tuple[str, str]] = []

    def visit(pack_id: str, version: str, depth: int) -> None:
        key = (pack_id, version)
        previous = selected.get(pack_id)
        if previous is not None and previous != version:
            raise DomainPackRegistryError(
                f"Domain Pack dependency version conflict: {pack_id} {previous} vs {version}"
            )
        selected[pack_id] = version
        if key in active:
            start = active.index(key)
            cycle = " -> ".join(item[0] for item in [*active[start:], key])
            raise DomainPackRegistryError(f"Domain Pack dependency cycle: {cycle}")
        depths[key] = max(depths.get(key, 0), depth)
        if key in resolved:
            return
        active.append(key)
        pack = registry.resolve(pack_id, version)
        resolved[key] = pack
        for dependency in pack.manifest.document["dependencies"]:
            visit(dependency["pack_id"], dependency["pack_version"], depth + 1)
            target = resolved[(dependency["pack_id"], dependency["pack_version"])]
            if target.lock.content_digest != dependency["content_digest"]:
                raise DomainPackRegistryError(
                    f"dependency lock digest mismatch: {dependency['pack_id']}"
                )
            missing = sorted(
                set(dependency["required_capabilities"])
                - set(target.manifest.capabilities)
            )
            if missing:
                raise DomainPackRegistryError(
                    f"dependency lacks required capabilities: {dependency['pack_id']} ({', '.join(missing)})"
                )
        active.pop()

    for pack_id, version in sorted(roots):
        visit(pack_id, version, 0)
    return tuple(
        replace(pack, dependency_depth=depths[key])
        for key, pack in sorted(resolved.items())
    )
