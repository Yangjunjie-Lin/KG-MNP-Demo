"""Local Plugin Registry with explicit external-code enablement."""

from __future__ import annotations

import importlib
from dataclasses import replace
from typing import Any

from .discovery import discover_builtin_plugins, discover_external_plugins
from .errors import PluginManifestError, PluginUnavailableError
from .models import PluginDescriptor, PluginStatus


class PluginRegistry:
    def __init__(
        self,
        descriptors: tuple[PluginDescriptor, ...] | None = None,
        *,
        discover_external: bool = True,
        allowlist: tuple[str, ...] = (),
    ) -> None:
        found = list(descriptors or discover_builtin_plugins())
        if descriptors is None and discover_external:
            found.extend(discover_external_plugins())
        duplicate_ids = sorted(
            plugin_id for plugin_id in {item.plugin_id for item in found}
            if sum(item.plugin_id == plugin_id for item in found) > 1
        )
        if duplicate_ids:
            raise PluginManifestError(f"duplicate Plugin ID(s): {', '.join(duplicate_ids)}")
        allowed = set(allowlist)
        self._descriptors: dict[str, PluginDescriptor] = {}
        for descriptor in found:
            if not descriptor.builtin and descriptor.plugin_id in allowed and descriptor.status == PluginStatus.DISABLED:
                descriptor = replace(
                    descriptor,
                    status=PluginStatus.ENABLED,
                    status_reason="external installed code explicitly allowlisted",
                )
            self._descriptors[descriptor.plugin_id] = descriptor

    def list(self) -> tuple[PluginDescriptor, ...]:
        return tuple(self._descriptors[key] for key in sorted(self._descriptors))

    def get(self, plugin_id: str) -> PluginDescriptor:
        try:
            return self._descriptors[plugin_id]
        except KeyError as exc:
            raise PluginUnavailableError(f"unknown Plugin: {plugin_id}") from exc

    def enable(self, plugin_id: str) -> PluginDescriptor:
        descriptor = self.get(plugin_id)
        if descriptor.status not in {PluginStatus.DISABLED, PluginStatus.VALID, PluginStatus.ENABLED}:
            raise PluginUnavailableError(
                f"Plugin {plugin_id} cannot be enabled: {descriptor.status}: {descriptor.status_reason}"
            )
        enabled = replace(
            descriptor,
            status=PluginStatus.ENABLED,
            status_reason="explicitly enabled",
        )
        self._descriptors[plugin_id] = enabled
        return enabled

    def load(self, plugin_id: str) -> Any:
        descriptor = self.get(plugin_id)
        if descriptor.status != PluginStatus.ENABLED:
            raise PluginUnavailableError(f"Plugin {plugin_id} is not enabled")
        if descriptor.builtin:
            module_name, object_name = descriptor.manifest["entry_point"]["object"].split(":", 1)
            module = importlib.import_module(module_name)
            target: Any = module
            for part in object_name.split("."):
                target = getattr(target, part)
            return target() if isinstance(target, type) else target
        target = descriptor.entry_point.load()
        return target() if isinstance(target, type) else target
