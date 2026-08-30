"""Deterministic JSON primitives used by Stage 04 modeling artifacts.

This is the deliberately small ``KG-MNP Canonical JSON v1`` profile.  It is
not an implementation of RFC 8785: numbers retain Python's JSON rendering and
callers must supply JSON-compatible values.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

CANONICAL_JSON_PROFILE = "KG-MNP Canonical JSON v1"


def canonical_json_bytes(value: Any) -> bytes:
    """Return stable UTF-8 JSON bytes for *value*.

    Object keys are sorted, insignificant whitespace is removed, Unicode is
    emitted directly, and non-finite floating-point values are rejected.
    """

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


def stable_urn(kind: str, value: Any) -> str:
    """Mint a deterministic KG-MNP URN from semantic content."""

    if not kind or any(character not in "abcdefghijklmnopqrstuvwxyz-" for character in kind):
        raise ValueError(f"invalid stable URN kind: {kind!r}")
    return f"urn:kg-mnp:{kind}:{semantic_hash(value)}"

