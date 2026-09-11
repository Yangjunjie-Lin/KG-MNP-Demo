from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..modeling.canonical_json import canonical_json_bytes


class GraphDBDataError(ValueError):
    pass


def unique_json(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GraphDBDataError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    except (OSError, UnicodeError, json.JSONDecodeError, GraphDBDataError) as exc:
        raise GraphDBDataError(f"cannot read JSON document {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GraphDBDataError(f"JSON document must be an object: {path}")
    return value


def json_bytes(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def safe_relative_path(value: str) -> str:
    from pathlib import PurePosixPath, PureWindowsPath

    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        not value
        or "\\" in value
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in posix.parts
        or posix.as_posix() != value
    ):
        raise GraphDBDataError(f"unsafe relative artifact path: {value}")
    return value
