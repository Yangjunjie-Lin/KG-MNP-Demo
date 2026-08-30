"""Restricted JSON/YAML loading and atomic deterministic writes."""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .canonical import canonical_json_bytes
from .errors import DocumentError, DocumentTooLargeError, DuplicateKeyError

DEFAULT_MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_YAML_ALIASES = 64


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate mapping key: {key!r}")
        result[key] = value
    return result


class _RestrictedLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: _RestrictedLoader, node: yaml.MappingNode) -> dict[str, Any]:
    loader.flatten_mapping(node)
    pairs = loader.construct_pairs(node, deep=True)
    if any(not isinstance(key, str) for key, _value in pairs):
        raise DocumentError("mapping keys must be strings")
    return _pairs_no_duplicates(pairs)


_RestrictedLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _assert_json_value(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DocumentError(f"non-finite number at {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_json_value(item, f"{path}/{index}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise DocumentError(f"non-string mapping key at {path}")
            _assert_json_value(item, f"{path}/{key}")
        return
    raise DocumentError(f"non-JSON-compatible value at {path}: {type(value).__name__}")


def read_document(
    path: Path | str,
    *,
    max_bytes: int = DEFAULT_MAX_DOCUMENT_BYTES,
) -> Any:
    """Read a UTF-8 JSON/YAML document with duplicates and unsafe tags denied."""

    source = Path(path)
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise DocumentError(f"cannot stat document: {source.name}: {exc}") from exc
    if size > max_bytes:
        raise DocumentTooLargeError(
            f"document exceeds {max_bytes} bytes: {source.name} ({size})"
        )
    try:
        raw = source.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise DocumentError(f"cannot read UTF-8 document {source.name}: {exc}") from exc
    try:
        if source.suffix.casefold() == ".json":
            value = json.loads(
                text,
                object_pairs_hook=_pairs_no_duplicates,
                parse_constant=lambda token: (_ for _ in ()).throw(
                    DocumentError(f"non-finite JSON number: {token}")
                ),
            )
        else:
            if text.count("*") > MAX_YAML_ALIASES:
                raise DocumentError("YAML alias limit exceeded")
            value = yaml.load(text, Loader=_RestrictedLoader)
    except DocumentError:
        raise
    except (json.JSONDecodeError, yaml.YAMLError, UnicodeError) as exc:
        raise DocumentError(f"invalid document {source.name}: {exc}") from exc
    _assert_json_value(value)
    return value


def deterministic_json_bytes(value: Any, *, pretty: bool = True) -> bytes:
    """Return deterministic UTF-8 JSON with exactly one trailing newline."""

    _assert_json_value(value)
    if not pretty:
        return canonical_json_bytes(value) + b"\n"
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def atomic_write_bytes(path: Path | str, content: bytes) -> None:
    """Atomically replace one file without writing outside its resolved parent."""

    destination = Path(path)
    parent = destination.parent.resolve(strict=True)
    if destination.name in {"", ".", ".."}:
        raise DocumentError("invalid atomic-write destination")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path | str, value: Any) -> None:
    atomic_write_bytes(path, deterministic_json_bytes(value))
