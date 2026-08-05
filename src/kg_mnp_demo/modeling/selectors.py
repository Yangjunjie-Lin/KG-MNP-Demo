"""Finite, exact RFC 6901 selector support for cleaned data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class _Missing:
    pass


MISSING = _Missing()


def _tokens(pointer: str) -> list[str]:
    if pointer == "":
        return []
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError(f"not an RFC 6901 JSON Pointer: {pointer!r}")
    tokens: list[str] = []
    for raw in pointer[1:].split("/"):
        index = 0
        decoded = ""
        while index < len(raw):
            if raw[index] != "~":
                decoded += raw[index]
                index += 1
                continue
            if index + 1 >= len(raw) or raw[index + 1] not in "01":
                raise ValueError(f"invalid RFC 6901 escape in pointer: {pointer!r}")
            decoded += "~" if raw[index + 1] == "0" else "/"
            index += 2
        tokens.append(decoded)
    return tokens


def validate_json_pointer(pointer: str) -> None:
    _tokens(pointer)


def resolve_pointer(document: Any, pointer: str, default: Any = MISSING) -> Any:
    """Resolve one exact pointer without JSONPath, scripts, or wildcards."""

    current = document
    for token in _tokens(pointer):
        if isinstance(current, dict):
            if token not in current:
                return default
            current = current[token]
            continue
        if isinstance(current, list):
            if token == "-" or not token.isdigit():
                return default
            if len(token) > 1 and token.startswith("0"):
                return default
            index = int(token)
            if index >= len(current):
                return default
            current = current[index]
            continue
        return default
    return current


def pointer_exists(document: Any, pointer: str) -> bool:
    return resolve_pointer(document, pointer) is not MISSING


def escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def iter_leaf_fields(document: Any, pointer: str = "") -> Iterator[tuple[str, Any]]:
    """Yield deterministic leaf pointers below an arbitrary JSON value."""

    if isinstance(document, dict) and document:
        for key in sorted(document):
            child = f"{pointer}/{escape_pointer_token(str(key))}"
            yield from iter_leaf_fields(document[key], child)
        return
    if isinstance(document, list) and document:
        for index, item in enumerate(document):
            yield from iter_leaf_fields(item, f"{pointer}/{index}")
        return
    yield pointer, document


def json_value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise TypeError(f"value is not JSON-compatible: {type(value).__name__}")

