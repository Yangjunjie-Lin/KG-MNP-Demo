"""Fail-closed static and rendered-query validation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import parse_qsl, quote, unquote, urlsplit

from ..graphdb.identifiers import validate_repository_id
from .errors import ApplicationError, ErrorCode
from .policy import MAX_QUERY_TIMEOUT_SECONDS

FORBIDDEN_TOKENS = frozenset(
    {
        "INSERT",
        "DELETE",
        "CLEAR",
        "DROP",
        "CREATE",
        "LOAD",
        "MOVE",
        "COPY",
        "ADD",
        "SERVICE",
        "WITH",
        "USING",
    }
)
ALLOWED_QUERY_TYPES = frozenset({"SELECT", "ASK", "CONSTRUCT"})
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_GRAPH_VARIABLE = re.compile(r"(?<![?$])\bGRAPH\s+\?([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_GRAPH_IRI = re.compile(r"(?<![?$])\bGRAPH\s*<([^>]+)>", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"@@[A-Z0-9_]+@@")


def _code_view(query: str) -> str:
    """Mask comments, strings and IRIs before token inspection."""
    chars = list(query)
    i = 0
    mode: str | None = None
    quote = ""
    while i < len(chars):
        char = chars[i]
        if mode == "comment":
            if char in "\r\n":
                mode = None
            else:
                chars[i] = " "
            i += 1
            continue
        if mode == "iri":
            if char == ">":
                mode = None
            chars[i] = " "
            i += 1
            continue
        if mode == "string":
            if char == "\\":
                chars[i] = " "
                if i + 1 < len(chars):
                    chars[i + 1] = " "
                    i += 2
                    continue
            if query.startswith(quote, i):
                for index in range(i, min(i + len(quote), len(chars))):
                    chars[index] = " "
                i += len(quote)
                mode = None
                continue
            chars[i] = " "
            i += 1
            continue
        if char == "#":
            mode = "comment"
            chars[i] = " "
            i += 1
            continue
        if char == "<":
            mode = "iri"
            chars[i] = " "
            i += 1
            continue
        if query.startswith("'''", i) or query.startswith('\"\"\"', i):
            quote = query[i : i + 3]
            mode = "string"
            chars[i : i + 3] = [" ", " ", " "]
            i += 3
            continue
        if char in {"'", '"'}:
            quote = char
            mode = "string"
            chars[i] = " "
            i += 1
            continue
        i += 1
    return "".join(chars)


def query_type(query: str) -> str:
    code = _code_view(query)
    tokens = [match.group(0).upper() for match in _WORD.finditer(code)]
    for token in tokens:
        if token in ALLOWED_QUERY_TYPES:
            return token
    raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)


def graph_variables_in(query: str) -> tuple[str, ...]:
    return tuple(sorted(set(_GRAPH_VARIABLE.findall(_code_view(query)))))


def graph_iris_in(query: str) -> tuple[str, ...]:
    return tuple(sorted(set(_GRAPH_IRI.findall(query))))


def require_graph_binding_placeholder(query: str, variable: str) -> None:
    marker = re.escape(f"@@GRAPH_{variable}@@")
    pattern = re.compile(
        rf"\bVALUES\s+\?{re.escape(variable)}\s*\{{\s*{marker}\s*\}}",
        re.IGNORECASE,
    )
    if len(pattern.findall(query)) != 1:
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)


def validate_bound_graph_values(
    query: str, bindings: dict[str, tuple[str, ...]]
) -> None:
    for variable, expected in bindings.items():
        pattern = re.compile(
            rf"\bVALUES\s+\?{re.escape(variable)}\s*\{{(?P<body>[^{{}}]*)\}}",
            re.IGNORECASE,
        )
        matches = list(pattern.finditer(query))
        if len(matches) != 1:
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        body = matches[0].group("body")
        iris = re.findall(r"<([^>]+)>", body)
        residue = re.sub(r"<[^>]+>", "", body)
        if residue.strip() or tuple(sorted(iris)) != tuple(sorted(expected)):
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)


def validate_query_text(
    query: str,
    *,
    allowed_types: Iterable[str],
    graph_variables: Iterable[str],
    allowed_graph_iris: Iterable[str] = (),
    allow_placeholders: bool = False,
) -> str:
    if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > 65536:
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
    code = _code_view(query)
    tokens = {match.group(0).upper() for match in _WORD.finditer(code)}
    if tokens & FORBIDDEN_TOKENS:
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
    if "FROM" in tokens or "DESCRIBE" in tokens:
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
    actual_type = query_type(query)
    if actual_type not in {item.upper() for item in allowed_types}:
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
    declared_variables = set(graph_variables)
    accessed_variables = set(_GRAPH_VARIABLE.findall(code))
    if accessed_variables != declared_variables:
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
    allowed_iris = set(allowed_graph_iris)
    if set(_GRAPH_IRI.findall(query)) - allowed_iris:
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
    placeholders = set(_PLACEHOLDER.findall(query))
    if placeholders and not allow_placeholders:
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
    if not re.search(r"(?<![?$])\bGRAPH\b", code, re.IGNORECASE):
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
    return actual_type


def _transport_target(path: str) -> tuple[str, list[tuple[str, str]]]:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
    try:
        query = parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=2,
        )
    except (TypeError, ValueError) as exc:
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION) from exc
    return parsed.path, query


def _transport_repository_id(segment: str) -> str:
    try:
        repository_id = unquote(segment, encoding="utf-8", errors="strict")
        if quote(repository_id, safe="") != segment:
            raise ValueError("repository path segment is not canonical")
        validate_repository_id(repository_id)
    except Exception as exc:
        raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION) from exc
    return repository_id


def assert_readonly_http_request(
    method: str,
    path: str,
    content_type: str | None,
    *,
    body: bytes | None = None,
    accept: str | None = None,
) -> None:
    """Validate the complete RDF4J request target and any SPARQL body.

    This is the final transport boundary.  It intentionally repeats query
    validation so a caller cannot bypass ``select``/``ask`` by invoking the
    low-level request method directly.
    """

    normalized_method = method.upper()
    target_path, query = _transport_target(path)
    media_type = content_type.strip().lower() if isinstance(content_type, str) else None
    accepted_type = accept.strip().lower() if isinstance(accept, str) else None
    if normalized_method == "GET" and target_path == "/rest/repositories":
        if (
            query
            or body is not None
            or media_type is not None
            or accepted_type != "application/json"
        ):
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        return
    repository_match = re.fullmatch(r"/rest/repositories/([^/]+)", target_path)
    if normalized_method == "GET" and repository_match:
        _transport_repository_id(repository_match.group(1))
        if (
            query
            or body is not None
            or media_type is not None
            or accepted_type != "application/json"
        ):
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        return
    statements_match = re.fullmatch(r"/repositories/([^/]+)/statements", target_path)
    if normalized_method == "GET" and statements_match:
        _transport_repository_id(statements_match.group(1))
        if (
            query != [("infer", "false")]
            or body is not None
            or media_type is not None
            or accepted_type != "application/n-quads"
        ):
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        return
    query_match = re.fullmatch(r"/repositories/([^/]+)", target_path)
    if (
        normalized_method == "POST"
        and query_match
        and media_type == "application/sparql-query"
        and accepted_type == "application/sparql-results+json"
    ):
        _transport_repository_id(query_match.group(1))
        if len(query) != 1 or query[0][0] != "timeout":
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        try:
            timeout = int(query[0][1])
        except (TypeError, ValueError) as exc:
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION) from exc
        if str(timeout) != query[0][1] or not 0 < timeout <= MAX_QUERY_TIMEOUT_SECONDS:
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        if not isinstance(body, bytes):
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        try:
            query_text = body.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION) from exc
        validate_query_text(
            query_text,
            allowed_types=("SELECT", "ASK"),
            graph_variables=graph_variables_in(query_text),
            allowed_graph_iris=graph_iris_in(query_text),
        )
        return
    raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
