"""Plugin-package entry points for Prompt 4 proposal-only providers."""

from zhigou_toolchain.modeling.control_plane.providers.builtin import (
    BaselineReuseProvider,
    ManualCandidateProvider,
    RecordedModelOutputProvider,
    RuleMappingProvider,
)

__all__ = [
    "BaselineReuseProvider",
    "ManualCandidateProvider",
    "RecordedModelOutputProvider",
    "RuleMappingProvider",
]
