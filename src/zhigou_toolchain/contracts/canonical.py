"""Deterministic canonical JSON and digest primitives."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CANONICAL_JSON_PROFILE = "KG-MNP Canonical JSON v1"


def canonical_json_bytes(value: Any) -> bytes:
    """Encode JSON data with stable keys, UTF-8, and no non-finite numbers."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def semantic_hash(value: Any) -> str:
    """Return the lowercase SHA-256 of the canonical semantic value."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def file_sha256(path: Path | str) -> str:
    """Return the lowercase SHA-256 of the exact bytes in *path*."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bytes_sha256(value: bytes) -> str:
    """Return the lowercase SHA-256 of bytes."""

    return hashlib.sha256(value).hexdigest()


def stable_urn(kind: str, value: Any) -> str:
    """Mint a deterministic KG-MNP URN from semantic content."""

    if not kind or any(char not in "abcdefghijklmnopqrstuvwxyz-" for char in kind):
        raise ValueError(f"invalid stable URN kind: {kind!r}")
    return f"urn:kg-mnp:{kind}:{semantic_hash(value)}"


def canonical_lock_preimage(value: dict[str, Any], *excluded: str) -> dict[str, Any]:
    """Return a shallow lock preimage with self-referential fields removed."""

    omitted = set(excluded)
    return {key: item for key, item in value.items() if key not in omitted}

