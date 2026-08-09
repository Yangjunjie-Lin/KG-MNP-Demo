"""Minimal GraphDB client whose public surface contains no write operations."""

from __future__ import annotations

import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from ..graphdb.identifiers import validate_repository_id
from .errors import ApplicationError, ErrorCode
from .policy import MAX_QUERY_TIMEOUT_SECONDS, MAX_RESPONSE_BODY_BYTES
from .query_validator import (
    assert_readonly_http_request,
    graph_iris_in,
    graph_variables_in,
    validate_query_text,
)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ApplicationError(ErrorCode.INTERNAL_ERROR)
        result[key] = value
    return result


class ReadOnlyGraphDBClient:
    """Only health, repository metadata, SELECT and ASK.

    No CONSTRUCT query is registered in Phase 01, so no CONSTRUCT method exists.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:7200", *, timeout: float = 5.0):
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        if not 0 < float(timeout) <= MAX_QUERY_TIMEOUT_SECONDS:
            raise ApplicationError(ErrorCode.INVALID_PARAMETER)
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
        accept: str = "application/json",
        timeout: float | None = None,
    ) -> tuple[int, bytes, str]:
        assert_readonly_http_request(method, path.split("?", 1)[0], content_type)
        if body is not None and len(body) > 65536:
            raise ApplicationError(ErrorCode.READ_ONLY_POLICY_VIOLATION)
        request = Request(
            self.base_url + path,
            data=body,
            method=method.upper(),
            headers={
                "Accept": accept,
                **({"Content-Type": content_type} if content_type else {}),
            },
        )
        try:
            with urlopen(request, timeout=timeout or self.timeout) as response:
                data = response.read(MAX_RESPONSE_BODY_BYTES + 1)
                if len(data) > MAX_RESPONSE_BODY_BYTES:
                    raise ApplicationError(ErrorCode.RESULT_LIMIT_EXCEEDED)
                return response.status, data, response.headers.get("Content-Type", "")
        except (socket.timeout, TimeoutError) as exc:
            raise ApplicationError(ErrorCode.QUERY_TIMEOUT) from exc
        except (HTTPError, URLError, OSError) as exc:
            raise ApplicationError(ErrorCode.GRAPHDB_UNAVAILABLE) from exc

    def health(self) -> dict[str, Any]:
        status, body, _ = self._request("GET", "/rest/repositories")
        if status != 200:
            raise ApplicationError(ErrorCode.GRAPHDB_UNAVAILABLE)
        try:
            payload = json.loads(body.decode("utf-8"), object_pairs_hook=_unique)
        except Exception as exc:
            raise ApplicationError(ErrorCode.GRAPHDB_UNAVAILABLE) from exc
        return {"healthy": True, "repository_count": len(payload) if isinstance(payload, list) else 0}

    def repository_info(self, repository_id: str) -> dict[str, Any]:
        validate_repository_id(repository_id)
        status, body, _ = self._request(
            "GET", "/rest/repositories/" + quote(repository_id, safe="")
        )
        if status != 200:
            raise ApplicationError(ErrorCode.GRAPHDB_UNAVAILABLE)
        try:
            value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique)
        except Exception as exc:
            raise ApplicationError(ErrorCode.GRAPHDB_UNAVAILABLE) from exc
        if not isinstance(value, dict):
            raise ApplicationError(ErrorCode.GRAPHDB_UNAVAILABLE)
        return value

    def _query(self, repository_id: str, query: str, *, query_kind: str, timeout: float) -> tuple[bytes, str]:
        validate_repository_id(repository_id)
        validate_query_text(
            query,
            allowed_types=(query_kind,),
            graph_variables=graph_variables_in(query),
            allowed_graph_iris=graph_iris_in(query),
        )
        if not 0 < timeout <= MAX_QUERY_TIMEOUT_SECONDS:
            raise ApplicationError(ErrorCode.INVALID_PARAMETER)
        path = "/repositories/" + quote(repository_id, safe="") + "?" + urlencode({"timeout": int(timeout)})
        accept = "application/sparql-results+json" if query_kind in {"SELECT", "ASK"} else "application/n-quads"
        status, body, content_type = self._request(
            "POST",
            path,
            body=query.encode("utf-8"),
            content_type="application/sparql-query",
            accept=accept,
            timeout=timeout,
        )
        if status >= 300:
            raise ApplicationError(ErrorCode.GRAPHDB_UNAVAILABLE)
        return body, content_type

    def select(self, repository_id: str, query: str, *, timeout: float = 5.0) -> dict[str, Any]:
        body, _ = self._query(repository_id, query, query_kind="SELECT", timeout=timeout)
        try:
            value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique)
        except Exception as exc:
            raise ApplicationError(ErrorCode.INTERNAL_ERROR) from exc
        if not isinstance(value, dict) or "results" not in value:
            raise ApplicationError(ErrorCode.INTERNAL_ERROR)
        return value

    def ask(self, repository_id: str, query: str, *, timeout: float = 5.0) -> bool:
        body, _ = self._query(repository_id, query, query_kind="ASK", timeout=timeout)
        try:
            value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique)
        except Exception as exc:
            raise ApplicationError(ErrorCode.INTERNAL_ERROR) from exc
        if not isinstance(value, dict) or not isinstance(value.get("boolean"), bool):
            raise ApplicationError(ErrorCode.INTERNAL_ERROR)
        return value["boolean"]
