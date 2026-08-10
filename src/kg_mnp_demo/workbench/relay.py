"""Narrow fixed-upstream relay to the frozen Phase 01 read-only API."""

from __future__ import annotations

import http.client
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode, urlsplit

from kg_mnp_demo.application.contracts import validate_application_contract

from .binding import WorkbenchBinding
from .contracts import strict_json_bytes
from .errors import WorkbenchError, WorkbenchErrorCode
from .policy import ALLOWED_PHASE01_ROUTES, load_workbench_policy


ROUTE_QUERY_IDS = {
    "/api/v1/ontology/classes": "ontology.classes",
    "/api/v1/ontology/properties": "ontology.properties",
    "/api/v1/ontology/term": "ontology.term",
    "/api/v1/entity": "business.entity",
    "/api/v1/entity/provenance": "provenance.entity",
    "/api/v1/fact": "business.fact",
    "/api/v1/fact/provenance": "provenance.fact",
    "/api/v1/review-trace": "review.trace",
    "/api/v1/source-trace": "source.trace",
    "/api/v1/evidence-trace": "evidence.trace",
    "/api/v1/trace": "trace.resource",
}

ROUTE_PARAMETERS = {
    "/api/v1/health": frozenset(),
    "/api/v1/ontology/classes": frozenset({"limit", "offset"}),
    "/api/v1/ontology/properties": frozenset({"limit", "offset"}),
    "/api/v1/ontology/term": frozenset({"iri", "limit", "offset"}),
    "/api/v1/entity": frozenset({"iri", "limit", "offset"}),
    "/api/v1/entity/provenance": frozenset({"iri", "limit", "offset"}),
    "/api/v1/fact": frozenset(
        {
            "subject",
            "predicate",
            "object_type",
            "object_value",
            "datatype_iri",
            "language",
        }
    ),
    "/api/v1/fact/provenance": frozenset(
        {
            "subject",
            "predicate",
            "object_type",
            "object_value",
            "datatype_iri",
            "language",
            "limit",
            "offset",
        }
    ),
    "/api/v1/review-trace": frozenset({"resource_id", "limit", "offset"}),
    "/api/v1/source-trace": frozenset({"source_ref", "limit", "offset"}),
    "/api/v1/evidence-trace": frozenset(
        {"evidence_ref", "limit", "offset"}
    ),
    "/api/v1/trace": frozenset({"resource_id", "limit", "offset"}),
}


class Phase01Relay:
    """Send only exact GET requests to one startup-frozen loopback service."""

    def __init__(
        self,
        upstream: str,
        binding: WorkbenchBinding,
        *,
        timeout: float = 10.0,
    ) -> None:
        parsed = urlsplit(upstream)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.port is None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise WorkbenchError(WorkbenchErrorCode.WORKBENCH_NOT_READY)
        self._host = "127.0.0.1"
        self._port = parsed.port
        self._binding = binding
        self._timeout = timeout
        self._maximum_response_bytes = int(
            load_workbench_policy()["relay"]["maximum_response_bytes"]
        )

    @staticmethod
    def validate_request(
        method: str,
        path: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        if method not in {"GET", "HEAD"}:
            raise WorkbenchError(
                WorkbenchErrorCode.READ_ONLY_POLICY_VIOLATION
            )
        parsed = urlsplit(path)
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or parsed.path != path
            or path not in ALLOWED_PHASE01_ROUTES
        ):
            raise WorkbenchError(WorkbenchErrorCode.RELAY_ROUTE_FORBIDDEN)
        values = parameters or {}
        if not isinstance(values, Mapping) or not set(values) <= ROUTE_PARAMETERS[path]:
            raise WorkbenchError(WorkbenchErrorCode.INVALID_REQUEST)
        for key, value in values.items():
            if not isinstance(key, str) or not isinstance(value, (str, int)):
                raise WorkbenchError(WorkbenchErrorCode.INVALID_REQUEST)
            if isinstance(value, str) and len(value) > 4096:
                raise WorkbenchError(WorkbenchErrorCode.INVALID_REQUEST)

    def _request(
        self,
        path: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.validate_request("GET", path, parameters)
        query = urlencode(parameters or {}, doseq=False)
        target = path if not query else f"{path}?{query}"
        connection = http.client.HTTPConnection(
            self._host,
            self._port,
            timeout=self._timeout,
        )
        try:
            connection.request(
                "GET",
                target,
                headers={
                    "Accept": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            response = connection.getresponse()
            content_type = response.getheader("Content-Type", "")
            raw = response.read(self._maximum_response_bytes + 1)
        except (OSError, http.client.HTTPException) as exc:
            raise WorkbenchError(WorkbenchErrorCode.PHASE01_UNAVAILABLE) from exc
        finally:
            connection.close()
        if (
            response.status != 200
            or len(raw) > self._maximum_response_bytes
            or "application/json" not in content_type.casefold()
        ):
            raise WorkbenchError(WorkbenchErrorCode.PHASE01_RESPONSE_INVALID)
        try:
            payload = strict_json_bytes(raw)
        except ValueError as exc:
            raise WorkbenchError(
                WorkbenchErrorCode.PHASE01_RESPONSE_INVALID
            ) from exc
        if not isinstance(payload, dict):
            raise WorkbenchError(WorkbenchErrorCode.PHASE01_RESPONSE_INVALID)
        return payload

    def health(self) -> dict[str, Any]:
        health = self._request("/api/v1/health")
        self._binding.verify_health(health)
        return health

    def query(
        self,
        path: str,
        parameters: Mapping[str, Any],
    ) -> dict[str, Any]:
        if path == "/api/v1/health":
            raise WorkbenchError(WorkbenchErrorCode.RELAY_ROUTE_FORBIDDEN)
        self.health()
        payload = self._request(path, parameters)
        try:
            validate_application_contract("query-result", payload)
        except Exception as exc:
            raise WorkbenchError(
                WorkbenchErrorCode.PHASE01_RESPONSE_INVALID
            ) from exc
        if payload.get("query_id") != ROUTE_QUERY_IDS.get(path):
            raise WorkbenchError(WorkbenchErrorCode.PHASE01_RESPONSE_INVALID)
        self._binding.verify_query_result(payload)
        return payload
