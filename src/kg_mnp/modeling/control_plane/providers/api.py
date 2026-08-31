"""Runtime-checkable proposal-only Modeling Provider protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import ImmutableModelingProviderRequest


@runtime_checkable
class ModelingProviderPlugin(Protocol):
    def propose(self, request: ImmutableModelingProviderRequest) -> tuple[dict, ...]: ...
