"""Small typing surface for lifecycle records.

Records remain JSON objects so the public contract catalog is the source of
truth; these aliases make the Python API pleasant without introducing a
second mutable model hierarchy.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias

LifecycleArtifact: TypeAlias = dict[str, Any]
ReadOnlyArtifact: TypeAlias = Mapping[str, Any]

PACKAGE_STATES = ("VALIDATED_UNPUBLISHED", "IMPORTED_VERIFIED")
RELEASE_STATES = ("RELEASED",)
ENVIRONMENT_SELECTION_STATES = ("NO_RELEASE_SELECTED", "CONTROL_PLANE_SELECTED")

__all__ = ["ENVIRONMENT_SELECTION_STATES", "PACKAGE_STATES", "RELEASE_STATES", "LifecycleArtifact", "ReadOnlyArtifact"]
