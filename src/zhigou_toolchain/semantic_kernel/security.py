"""Offline input, IRI, path, query, and package safety checks."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from .errors import SemanticKernelError

_LANGUAGE = re.compile(r"^[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*$")
_SAFE_PACKAGE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SECRET_KEY = re.compile(r"(?:api[_-]?key|secret|password|private[_-]?key|access[_-]?token)", re.IGNORECASE)
_QUERY_FORBIDDEN = re.compile(
    r"\b(?:UPDATE|INSERT|DELETE|LOAD|CLEAR|DROP|CREATE|MOVE|COPY|ADD|SERVICE)\b|"
    r"\bFROM\s+(?:NAMED\s+)?<(?:(?:https?|file):)",
    re.IGNORECASE,
)


def validate_iri(value: str, *, label: str = "IRI") -> str:
    if not isinstance(value, str) or len(value) > 2048 or any(ch.isspace() for ch in value):
        raise SemanticKernelError(f"invalid {label}")
    parsed = urlsplit(value)
    if parsed.scheme == "https":
        if not parsed.netloc or parsed.username is not None or parsed.password is not None:
            raise SemanticKernelError(f"unsafe {label}")
    elif parsed.scheme == "http" and parsed.netloc in {"www.w3.org", "purl.org"}:
        pass
    elif parsed.scheme == "urn":
        if not parsed.path or ":" not in value:
            raise SemanticKernelError(f"invalid {label}")
    else:
        raise SemanticKernelError(f"unsafe {label} scheme")
    if any(token in value for token in ("<", ">", '"', "{", "}", "|", "\\", "^", "`")):
        raise SemanticKernelError(f"unsafe {label} characters")
    return value


def validate_language(value: str | None) -> str | None:
    if value is not None and not _LANGUAGE.fullmatch(value):
        raise SemanticKernelError("invalid RDF language tag")
    return value


def validate_package_name(value: str) -> str:
    if len(value) > 128 or not _SAFE_PACKAGE.fullmatch(value):
        raise SemanticKernelError("package name must be safe kebab-case", code="COMPILATION_PLAN_INVALID")
    return value


def validate_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise SemanticKernelError("unsafe relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise SemanticKernelError("path traversal or absolute path rejected")
    if re.match(r"^[A-Za-z]:", value) or value.startswith("//"):
        raise SemanticKernelError("Windows or UNC path rejected")
    return value


def safe_child(root: Path, relative: str, *, must_exist: bool = False) -> Path:
    validate_relative_path(relative)
    resolved_root = root.resolve(strict=True)
    unresolved = resolved_root / PurePosixPath(relative)
    current = resolved_root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise SemanticKernelError("symlink artifact rejected")
    candidate = unresolved.resolve(strict=must_exist)
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise SemanticKernelError("path escapes trusted root")
    return candidate


def assert_safe_json(value: Any, *, depth: int = 0) -> None:
    if depth > 64:
        raise SemanticKernelError("JSON nesting limit exceeded")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or _SECRET_KEY.search(key):
                raise SemanticKernelError("secret-bearing or invalid JSON key rejected")
            assert_safe_json(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            assert_safe_json(item, depth=depth + 1)
    elif isinstance(value, str):
        if "\x00" in value:
            raise SemanticKernelError("NUL text rejected")
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise SemanticKernelError("unsupported JSON value")


def assert_read_only_query(
    query: str,
    *,
    max_characters: int = 100_000,
    max_path_depth: int = 8,
) -> str:
    if not isinstance(query, str) or not query.strip() or len(query) > max_characters:
        raise SemanticKernelError("query is empty or exceeds its character limit", code="COMPETENCY_QUESTION_FAILED")
    lexical=re.compile("|".join([r'<[^<>\s]*>',r'"""(?:\\.|(?!""").)*"""',r"'''(?:\\.|(?!''').)*'''",r'"(?:\\.|[^"\\])*"',r"'(?:\\.|[^'\\])*'",r'#[^\r\n]*']),re.DOTALL)  # noqa: FLY002 - explicit lexical alternatives
    structural=lexical.sub(" ",query)
    if _QUERY_FORBIDDEN.search(structural) or re.search(r"\bFROM\b",structural,re.IGNORECASE):
        raise SemanticKernelError("unsafe or non-read-only SPARQL query", code="COMPETENCY_QUESTION_FAILED")
    try:
        from rdflib.plugins.sparql.parser import parseQuery
        parsed=parseQuery(query)
        operation={"AskQuery":"ASK","SelectQuery":"SELECT","ConstructQuery":"CONSTRUCT"}[parsed[1].name]
    except Exception as exc:
        raise SemanticKernelError("invalid or unsupported read-only SPARQL query",code="COMPETENCY_QUESTION_FAILED") from exc
    path_tokens = re.findall(r"(?<![?])[/|^*+]", structural)
    if len(path_tokens) > max_path_depth:
        raise SemanticKernelError("SPARQL property-path complexity limit exceeded", code="COMPETENCY_QUESTION_FAILED")
    return operation


def scan_prohibited_text(data: bytes) -> list[str]:
    text = data.decode("utf-8", errors="ignore")
    findings = []
    if re.search(r"(?:[A-Za-z]:\\|\\\\[^\\]+\\|/home/|/Users/)", text):
        findings.append("ABSOLUTE_PATH_LEAKAGE")
    if re.search(r"(?:AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----)", text):
        findings.append("SECRET_LEAKAGE")
    return findings
