"""Core-owned provider execution and response validation."""

from __future__ import annotations

from zhigou_toolchain.plugins.registry import PluginRegistry

from ..errors import ModelingProviderError
from ..security import assert_safe_json
from .api import ModelingProviderPlugin
from .models import ImmutableModelingProviderRequest, build_provider_response


def execute_provider(
    registry: PluginRegistry,
    provider_id: str,
    request: ImmutableModelingProviderRequest,
) -> dict:
    descriptor = registry.get(provider_id)
    if descriptor.manifest.get("authority_level") != "PROPOSAL_ONLY":
        raise ModelingProviderError("modeling provider lacks PROPOSAL_ONLY authority declaration")
    if descriptor.manifest.get("network_policy") != "DENY" or "NETWORK" in descriptor.manifest.get("side_effects", []):
        raise ModelingProviderError("network-enabled modeling provider is rejected")
    if not descriptor.enabled:
        raise ModelingProviderError("modeling provider is disabled")
    plugin = registry.load(provider_id)
    if not isinstance(plugin, ModelingProviderPlugin):
        raise ModelingProviderError("plugin does not implement ModelingProviderPlugin")
    try:
        drafts = plugin.propose(request)
    except Exception as exc:
        raise ModelingProviderError(f"modeling provider failed: {exc}") from exc
    if not isinstance(drafts, tuple):
        raise ModelingProviderError("modeling provider response must be an immutable tuple")
    assert_safe_json(drafts, provider_output=True)
    return build_provider_response(request, candidate_drafts=drafts)
