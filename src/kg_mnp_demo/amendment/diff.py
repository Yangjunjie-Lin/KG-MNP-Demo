"""Independent deterministic JSON-Pointer diffing for revised cleaned input."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def escape_json_pointer_token(token: str) -> str:
    return str(token).replace("~", "~0").replace("/", "~1")


def join_json_pointer(prefix: str, token: str | int) -> str:
    escaped = escape_json_pointer_token(str(token))
    return f"/{escaped}" if not prefix else f"{prefix}/{escaped}"


def _walk(left: Any, right: Any, pointer: str, result: set[str]) -> None:
    if type(left) is not type(right) and not (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        result.add(pointer or "")
        return
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        for key in sorted(set(left) | set(right), key=str):
            child = join_json_pointer(pointer, str(key))
            if key not in left or key not in right:
                result.add(child)
            else:
                _walk(left[key], right[key], child, result)
        return
    if isinstance(left, list) and isinstance(right, list):
        common = min(len(left), len(right))
        for index in range(common):
            _walk(
                left[index],
                right[index],
                join_json_pointer(pointer, str(index)),
                result,
            )
        for index in range(common, max(len(left), len(right))):
            result.add(join_json_pointer(pointer, str(index)))
        return
    if left != right:
        result.add(pointer or "")


def compute_json_diff(base: Any, revised: Any) -> list[str]:
    """Return sorted RFC-6901 pointers for every changed leaf/container."""

    result: set[str] = set()
    _walk(base, revised, "", result)
    return sorted(result)


def compute_cleaned_input_diff(
    base: Mapping[str, Any], revised: Mapping[str, Any]
) -> list[str]:
    """Compare all cleaned-data and metadata fields, including presence/evidence."""

    return compute_json_diff(base, revised)


def pointer_is_within(pointer: str, declared: str) -> bool:
    if pointer == declared:
        return True
    return bool(declared) and pointer.startswith(declared.rstrip("/") + "/")
