"""Security validation for untrusted KG-IR and provider JSON."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import urlsplit

from .errors import ModelingControlError, ModelingProviderError

ALLOWED_IRI_SCHEMES = frozenset({"https", "urn"})
RESERVED_NAMESPACES = (
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/2002/07/owl#",
    "http://www.w3.org/2001/XMLSchema#",
    "http://www.w3.org/ns/shacl#",
)
SECRET_KEY = re.compile(
    r"(?:api[_-]?key|authorization|password|passwd|secret|token|credential)",
    re.IGNORECASE,
)
SECRET_VALUE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._~+/-]{12,})",
    re.IGNORECASE,
)
ABSOLUTE_WINDOWS = re.compile(r"^[A-Za-z]:[\\/]")
FORBIDDEN_EXECUTABLE = (
    "sparql update", "insert data", "delete where", "prefix rdf:", "@prefix",
    "owl:functional", "subprocess", "os.system(", "powershell", "#!/bin/", "```python",
    "```shell", "```turtle", "__import__(", "eval(", "exec(", "{%", "{{",
)
CONFIRMED_PACKAGE_FORBIDDEN_KEYS = frozenset(
    {
        "publication_manifest",
        "publication_command",
        "graphdb_url",
        "rdf",
        "turtle",
        "owl_functional_syntax",
        "sparql_update",
        "shell",
        "python",
    }
)
CONFIRMED_PACKAGE_FORBIDDEN_TEXT = (
    "@prefix",
    "prefix rdf:",
    "insert data",
    "delete where",
    "sparql update",
    "```turtle",
    "```python",
    "```shell",
    "#!/bin/",
    "graphdb://",
)


def json_depth(value: Any) -> int:
    if isinstance(value, Mapping):
        return 1 + max((json_depth(item) for item in value.values()), default=0)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return 1 + max((json_depth(item) for item in value), default=0)
    return 1


def has_mixed_script_confusable(value: str) -> bool:
    """Flag common Latin/Greek/Cyrillic mixtures for mandatory human attention."""

    scripts: set[str] = set()
    for character in value:
        if not character.isalpha():
            continue
        name = unicodedata.name(character, "")
        for script in ("LATIN", "GREEK", "CYRILLIC"):
            if script in name:
                scripts.add(script)
                break
    return len(scripts) > 1


def _safe_string(value: str, *, provider_output: bool) -> None:
    if unicodedata.normalize("NFC", value) != value:
        raise ModelingControlError("text must be Unicode NFC")
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in value):
        raise ModelingControlError("Unicode control/format characters are rejected")
    if ABSOLUTE_WINDOWS.match(value) or value.startswith(("/", "\\\\", "file:")):
        raise ModelingControlError("absolute or local filesystem paths are rejected")
    if SECRET_VALUE.search(value):
        raise ModelingControlError("secret-like value is rejected")
    if provider_output and any(token in value.casefold() for token in FORBIDDEN_EXECUTABLE):
        raise ModelingProviderError("provider output contains executable or RDF syntax")


def assert_safe_json(
    value: Any,
    *,
    provider_output: bool = False,
    max_bytes: int = 4 * 1024 * 1024,
    max_depth: int = 64,
) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    except (TypeError, ValueError) as exc:
        raise ModelingControlError(f"value is not finite JSON: {exc}") from exc
    if len(encoded) > max_bytes:
        raise ModelingControlError("JSON value exceeds the configured byte limit")
    if json_depth(value) > max_depth:
        raise ModelingControlError("JSON value exceeds the configured nesting limit")

    def visit(item: Any, path: str) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                if not isinstance(key, str):
                    raise ModelingControlError(f"non-string JSON key at {path}")
                _safe_string(key, provider_output=provider_output)
                if SECRET_KEY.search(key):
                    raise ModelingControlError(f"secret-bearing field rejected at {path}/{key}")
                if provider_output and key.casefold() in {
                    "candidate_id", "semantic_signature", "confirmed", "confirmation_status",
                    "review_decision", "accept", "project_lock", "project_lock_id",
                    "domain_pack_lock", "domain_pack_lock_ids", "publication_manifest",
                }:
                    raise ModelingProviderError(f"provider authority field rejected: {key}")
                visit(nested, f"{path}/{key}")
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for index, nested in enumerate(item):
                visit(nested, f"{path}/{index}")
        elif isinstance(item, str):
            _safe_string(item, provider_output=provider_output)

    visit(value, "$")


def validate_iri(
    value: str,
    *,
    allowed_schemes: set[str] | frozenset[str] = ALLOWED_IRI_SCHEMES,
    allowed_namespaces: tuple[str, ...] = (),
    reusable_namespaces: tuple[str, ...] = (),
    creating: bool = False,
) -> None:
    _safe_string(value, provider_output=False)
    split = urlsplit(value)
    scheme = split.scheme.casefold()
    standard_http_reference = (
        not creating
        and scheme == "http"
        and any(value.startswith(namespace) for namespace in RESERVED_NAMESPACES)
    )
    if scheme not in allowed_schemes and not standard_http_reference:
        raise ModelingControlError(f"IRI scheme is not allowed: {scheme or '<missing>'}")
    if scheme in {"http", "https"} and not split.netloc:
        raise ModelingControlError("HTTP(S) IRI requires an authority")
    if creating and any(value.startswith(namespace) for namespace in RESERVED_NAMESPACES):
        raise ModelingControlError("standard RDF/OWL/XSD/SHACL namespaces are read-only")
    if creating and allowed_namespaces and not any(value.startswith(item) for item in allowed_namespaces):
        raise ModelingControlError("candidate IRI is outside authorized namespaces")
    if not creating and reusable_namespaces and not any(value.startswith(item) for item in reusable_namespaces):
        raise ModelingControlError("external IRI is outside reusable namespaces")


def validate_safe_relative_path(value: str) -> None:
    _safe_string(value, provider_output=False)
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value)
    if windows.is_absolute() or posix.is_absolute() or ".." in windows.parts or ".." in posix.parts:
        raise ModelingControlError("unsafe relative artifact path")


def assert_confirmed_package_safe(value: dict[str, Any]) -> None:
    """Reject executable/publication payloads from the non-RDF confirmation package."""

    assert_safe_json(value)

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                if key.casefold() in CONFIRMED_PACKAGE_FORBIDDEN_KEYS:
                    raise ModelingControlError(f"confirmed package contains prohibited field: {key}")
                visit(nested)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for nested in item:
                visit(nested)
        elif isinstance(item, str):
            folded = item.casefold()
            if any(token in folded for token in CONFIRMED_PACKAGE_FORBIDDEN_TEXT):
                raise ModelingControlError("confirmed package contains executable, RDF, or publication text")

    visit(value)
