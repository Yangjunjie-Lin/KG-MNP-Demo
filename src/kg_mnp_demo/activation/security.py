"""Input and local-path boundaries for the Phase 06 control plane."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
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
_PATH_ATTACK = re.compile(r"(?:^|[\\/])\.\.(?:[\\/]|$)|%2e|%252e", re.IGNORECASE)


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


def freeze_state_directory(path: Path) -> Path:
    """Freeze one startup-configured local directory and reject path indirection."""

    supplied = Path(path)
    text = str(supplied)
    if _PATH_ATTACK.search(text):
        raise ActivationError(ActivationErrorCode.PATH_REJECTED)
    absolute = supplied.absolute()
    try:
        # Inspect the lexical path before resolution so a symlink/junction cannot
        # disappear behind ``resolve()`` and become a trusted state root.
        for candidate in (absolute, *absolute.parents):
            is_junction = getattr(candidate, "is_junction", lambda: False)
            if candidate.exists() and (candidate.is_symlink() or is_junction()):
                raise ActivationError(ActivationErrorCode.PATH_REJECTED)
        absolute.mkdir(parents=True, exist_ok=True)
        resolved = absolute.resolve(strict=True)
        for candidate in (absolute, *absolute.parents, resolved, *resolved.parents):
            is_junction = getattr(candidate, "is_junction", lambda: False)
            if candidate.is_symlink() or is_junction():
                raise ActivationError(ActivationErrorCode.PATH_REJECTED)
    except ActivationError:
        raise
    except OSError as exc:
        raise ActivationError(ActivationErrorCode.PATH_REJECTED) from exc
    return resolved
