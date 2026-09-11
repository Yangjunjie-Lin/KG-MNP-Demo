from __future__ import annotations

from .protocol import AdapterManifest, IntegrationTarget


class AdapterRegistry:
    def __init__(self):
        self._manifests: dict[str, AdapterManifest] = {}
        self._targets: dict[str, IntegrationTarget] = {}

    def register_manifest(self, manifest: AdapterManifest) -> None:
        if manifest.adapter_id in self._manifests:
            raise ValueError("adapter ID already registered")
        self._manifests[manifest.adapter_id] = manifest

    def register_target(self, target: IntegrationTarget) -> None:
        if not target.target_id or "://" in target.target_id:
            raise ValueError("target_id, not an endpoint URL, is required")
        self._targets[target.target_id] = target

    def manifest(self, adapter_id: str) -> AdapterManifest:
        return self._manifests[adapter_id]

    def target(self, target_id: str) -> IntegrationTarget:
        return self._targets[target_id]
