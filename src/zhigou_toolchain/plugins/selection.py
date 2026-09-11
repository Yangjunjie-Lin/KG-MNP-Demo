"""Deterministic, policy-bound provider selection."""

from __future__ import annotations

from fnmatch import fnmatchcase

from .errors import (
    AmbiguousProviderSelectionError,
    ProviderSelectionError,
)
from .models import PluginDescriptor, PluginStatus, ProviderSelection


def _media_matches(patterns: list[str], media_type: str) -> bool:
    return any(fnmatchcase(media_type, pattern.replace("*", "*")) for pattern in patterns)


def select_provider(
    descriptors: tuple[PluginDescriptor, ...],
    *,
    plugin_kind: str,
    capability: str,
    media_type: str,
    preference: str | None = None,
    offline: bool = True,
    strict_determinism: bool = True,
) -> ProviderSelection:
    eligible: list[PluginDescriptor] = []
    for descriptor in descriptors:
        manifest = descriptor.manifest
        if descriptor.status != PluginStatus.ENABLED:
            continue
        if manifest.get("plugin_api_version") != "1.0.0":
            continue
        if plugin_kind not in manifest.get("plugin_kinds", []):
            continue
        if capability not in manifest.get("capabilities", []):
            continue
        if not _media_matches(manifest.get("media_types", []), media_type):
            continue
        if offline and "NETWORK" in manifest.get("side_effects", []):
            continue
        if strict_determinism and manifest.get("determinism") == "NONDETERMINISTIC":
            continue
        eligible.append(descriptor)
    eligible.sort(key=lambda item: (-int(item.manifest["priority"]), item.plugin_id))
    if preference is not None:
        selected = [item for item in eligible if item.plugin_id == preference]
        if not selected:
            raise ProviderSelectionError(
                f"preferred provider {preference!r} is unavailable or policy-incompatible"
            )
        return ProviderSelection(selected[0], "explicit provider preference")
    if not eligible:
        raise ProviderSelectionError(
            f"MISSING_PROVIDER: {plugin_kind}/{capability}/{media_type}"
        )
    highest = int(eligible[0].manifest["priority"])
    tied = [item for item in eligible if int(item.manifest["priority"]) == highest]
    if len(tied) > 1:
        raise AmbiguousProviderSelectionError(
            "AMBIGUOUS_PROVIDER_SELECTION: " + ", ".join(item.plugin_id for item in tied)
        )
    return ProviderSelection(eligible[0], "highest unique policy-compliant priority")
