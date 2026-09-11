"""Plugin metadata and response security checks."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from zhigou_toolchain.contracts.errors import PathSecurityError
from zhigou_toolchain.contracts.identifiers import validate_safe_relative_path

from .errors import PluginConformanceError, PluginManifestError

_PLUGIN_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_ABSOLUTE = re.compile(r"(?:^[A-Za-z]:[\\/]|^\\\\|^/)")
_SECRET_WORDS = ("password", "passwd", "secret", "token", "api_key", "private_key")


def validate_plugin_id(value: str) -> str:
    if not isinstance(value, str) or not _PLUGIN_ID.fullmatch(value):
        raise PluginManifestError(f"unsafe plugin_id: {value!r}")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise PluginManifestError(f"unsafe plugin_id: {value!r}")
    return value


def validate_implementation_files(root: Path, files: list[str]) -> tuple[Path, ...]:
    root_resolved = root.resolve(strict=True)
    resolved: list[Path] = []
    for relative in files:
        try:
            validate_safe_relative_path(relative)
        except PathSecurityError as exc:
            raise PluginManifestError(f"unsafe implementation file: {relative!r}") from exc
        candidate = root_resolved.joinpath(*relative.split("/"))
        try:
            target = candidate.resolve(strict=True)
            target.relative_to(root_resolved)
        except (OSError, RuntimeError, ValueError) as exc:
            raise PluginManifestError(
                f"implementation file escapes or is missing: {relative}"
            ) from exc
        if not target.is_file() or target.is_symlink():
            raise PluginManifestError(f"implementation file is not a regular file: {relative}")
        resolved.append(target)
    return tuple(resolved)


def assert_safe_configuration(value: Any, path: str = "configuration") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or any(word in key.casefold() for word in _SECRET_WORDS):
                raise PluginManifestError(f"secret-like or invalid configuration key at {path}")
            assert_safe_configuration(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_safe_configuration(item, f"{path}[{index}]")
        return
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str) and _ABSOLUTE.search(value):
            raise PluginManifestError(f"absolute path in {path}")
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    raise PluginManifestError(f"unsafe configuration value at {path}")


def assert_safe_plugin_output(value: Any, *, max_characters: int = 16_000_000) -> None:
    text_budget = 0

    def walk(item: Any, path: str) -> None:
        nonlocal text_budget
        if isinstance(item, dict):
            forbidden = {"evidence_id", "item_id", "dataset_id", "artifact_id", "output_path"}
            intersection = forbidden.intersection(item)
            if intersection:
                raise PluginConformanceError(
                    f"Plugin output controls authoritative field(s): {sorted(intersection)}"
                )
            for key, nested in item.items():
                walk(nested, f"{path}.{key}")
        elif isinstance(item, (list, tuple)):
            for index, nested in enumerate(item):
                walk(nested, f"{path}[{index}]")
        elif isinstance(item, str):
            text_budget += len(item)
            if _ABSOLUTE.search(item) and not path.endswith(".locator.pointer"):
                raise PluginConformanceError(f"absolute path in Plugin output at {path}")
        elif isinstance(item, float) and not math.isfinite(item):
            raise PluginConformanceError(f"non-finite number in Plugin output at {path}")
        elif item is not None and not isinstance(item, (bool, int, float, bytes)):
            raise PluginConformanceError(f"unsupported Plugin output type at {path}")

    walk(value, "output")
    if text_budget > max_characters:
        raise PluginConformanceError("Plugin output character limit exceeded")
