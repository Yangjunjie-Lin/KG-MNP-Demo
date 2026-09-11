"""Input and local-path boundaries for the Phase 06 control plane."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .errors import ActivationError, ActivationErrorCode

_FORBIDDEN_KEYS = frozenset(
    {
        "activationauto",
        "authoritypath",
        "confirmedfact",
        "graphcommand",
        "graphdburl",
        "graphstorewrite",
        "insertdata",
        "pointerpath",
        "rdfpatch",
        "registrypath",
        "repositorycommand",
        "repositorydelete",
        "reviewdecision",
        "sparql",
        "sparqlupdate",
    }
)


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def exact_fields(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    """Return a plain object only when its field set is exactly closed."""

    if not isinstance(value, Mapping) or set(value) != fields:
        raise ActivationError(
            ActivationErrorCode.INVALID_ACTIVATION_REQUEST,
            f"{label} field set mismatch",
        )
    return dict(value)


def validate_control_plane_payload(value: Any) -> None:
    """Reject graph mutation, semantic escalation, and path injection fields."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            marker = _normalized_key(str(key))
            if marker in _FORBIDDEN_KEYS:
                raise ActivationError(
                    ActivationErrorCode.INVALID_ACTIVATION_REQUEST,
                    f"forbidden activation request field: {key}",
                )
            if marker == "semanticauthority" and child is not False:
                raise ActivationError(
                    ActivationErrorCode.INVALID_ACTIVATION_REQUEST,
                    "activation cannot claim semantic authority",
                )
            validate_control_plane_payload(child)
    elif isinstance(value, list):
        for child in value:
            validate_control_plane_payload(child)


def validate_operator_label(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ActivationError(
            ActivationErrorCode.INVALID_ACTIVATION_REQUEST,
            f"{field} must be a non-empty operator-supplied label",
        )
    return value.strip()
