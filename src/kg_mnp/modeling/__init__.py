"""Modeling contracts, proposal generation, human review, and confirmation.

The legacy Stage 04 implementation is repository-backed, while the Prompt 4
control plane is packaged for use outside a source checkout.  Keep the legacy
public exports available, but load them only when callers request them so that
importing :mod:`kg_mnp.modeling.control_plane` does not require repository
development assets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .confirmation import build_confirmed_modeling_package
    from .proposal import GENERATOR_VERSION, generate_modeling_proposal

__all__ = [
    "GENERATOR_VERSION",
    "build_confirmed_modeling_package",
    "generate_modeling_proposal",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve the repository-backed legacy public API."""

    if name == "build_confirmed_modeling_package":
        from .confirmation import build_confirmed_modeling_package

        return build_confirmed_modeling_package
    if name in {"GENERATOR_VERSION", "generate_modeling_proposal"}:
        from .proposal import GENERATOR_VERSION, generate_modeling_proposal

        return {
            "GENERATOR_VERSION": GENERATOR_VERSION,
            "generate_modeling_proposal": generate_modeling_proposal,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
