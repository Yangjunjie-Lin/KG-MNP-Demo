"""Public identifier and safe relative-path rules."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from .canonical import stable_urn
from .errors import PathSecurityError

_IDENTIFIER = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def normalize_identifier(value: str, *, label: str = "identifier") -> str:
    """Validate and return a lower kebab-case identifier."""

    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def validate_semver(value: str) -> str:
    """Validate a strict Semantic Version string."""

    if not isinstance(value, str) or not _SEMVER.fullmatch(value):
        raise ValueError(f"invalid semantic version: {value!r}")
    return value


def validate_safe_relative_path(value: str) -> PurePosixPath:
    """Validate a non-empty relative POSIX path without traversal syntax."""

    if not isinstance(value, str) or not value:
        raise PathSecurityError("relative path must be a non-empty string")
    if _CONTROL.search(value):
        raise PathSecurityError(f"relative path contains a control character: {value!r}")
    if "\\" in value:
        raise PathSecurityError(f"relative path must use POSIX separators: {value!r}")
    if value.startswith(('/', '//')) or re.match(r"^[A-Za-z]:", value):
        raise PathSecurityError(f"absolute path is forbidden: {value!r}")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise PathSecurityError(f"unsafe relative path segment: {value!r}")
    return PurePosixPath(*parts)


def resolve_within(root: Path, relative: str, *, must_exist: bool = True) -> Path:
    """Resolve *relative* beneath *root* and reject symlink/path escapes."""

    root_resolved = root.resolve(strict=True)
    candidate = root_resolved.joinpath(validate_safe_relative_path(relative))
    try:
        resolved = candidate.resolve(strict=must_exist)
    except (OSError, RuntimeError) as exc:
        raise PathSecurityError(f"cannot resolve safe path {relative!r}: {exc}") from exc
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise PathSecurityError(f"path escapes authority root: {relative!r}") from exc
    return resolved


def artifact_urn(value: Any) -> str:
    return stable_urn("artifact", value)


def pack_lock_urn(value: Any) -> str:
    return stable_urn("domain-pack-lock", value)


def project_lock_urn(value: Any) -> str:
    return stable_urn("project-lock", value)

