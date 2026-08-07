from __future__ import annotations

import json
import hashlib
import socket
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from rdflib import BNode, Graph

from ..compilation.rdf_canonical import canonical_ntriples

from ._io import unique_json
from .identifiers import validate_repository_id


class GraphDBClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class DefaultGraphSnapshot:
    http_status: int
    statement_count: int
    semantic_hash: str
    content_type: str


def redact_credentials(value: str) -> str:
    from urllib.parse import urlsplit
    parsed = urlsplit(value)
    if not parsed.hostname:
        return value
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    netloc = host
    if parsed.port:
        netloc += f":{parsed.port}"
    # Query strings can carry bearer tokens just as userinfo can carry a
    # password; diagnostics retain only the safe scheme/host/path.
    return f"{parsed.scheme}://{netloc}{parsed.path}"


@dataclass
class GraphDBClient:
    base_url: str = "http://127.0.0.1:7200"
    timeout: float = 10.0
    retries: int = 2
    allow_remote: bool = False
    max_response_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        value = self.base_url.rstrip("/")
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise GraphDBClientError("base URL must be an HTTP(S) URL")
        if parsed.username or parsed.password:
            raise GraphDBClientError("credentials in GraphDB base URL are forbidden")
        if not self.allow_remote and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise GraphDBClientError("remote GraphDB requires explicit allow_remote=True")
        if self.timeout <= 0 or self.retries < 0:
            raise GraphDBClientError("invalid timeout/retry policy")
        self.base_url = value

    def _request(self, method: str, path: str, *, body: bytes | None = None, content_type: str | None = None, accept: str | None = None, headers: Mapping[str, str] | None = None) -> tuple[int, bytes, Mapping[str, str]]:
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path
        request_headers = {"User-Agent": "kg-mnp-stage07/1.0", "Accept": accept or "*/*"}
        if content_type:
            request_headers["Content-Type"] = content_type
        if headers:
            request_headers.update(headers)
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                request = Request(url, data=body, headers=request_headers, method=method)
                with urlopen(request, timeout=self.timeout) as response:
                    payload = response.read(self.max_response_bytes + 1)
                    if len(payload) > self.max_response_bytes:
                        raise GraphDBClientError("GraphDB response exceeds size limit")
                    return response.status, payload, dict(response.headers.items())
            except HTTPError as exc:
                payload = exc.read(self.max_response_bytes + 1)
                raise GraphDBClientError(f"GraphDB HTTP {exc.code} for {method} {redact_credentials(url)}: {payload[:256]!r}") from exc
            except (URLError, TimeoutError, socket.timeout, GraphDBClientError) as exc:
                last = exc
                if isinstance(exc, GraphDBClientError) and "response exceeds" in str(exc):
                    raise
                if attempt < self.retries:
                    time.sleep(min(0.25 * (2 ** attempt), 1.0))
        raise GraphDBClientError(f"GraphDB request failed for {method} {redact_credentials(url)}: {last}") from last

    def health_check(self) -> dict[str, Any]:
        status, body, _ = self._request(
            "GET", "/rest/repositories", accept="application/json"
        )
        try:
            value = json.loads(body.decode("utf-8"), object_pairs_hook=unique_json)
        except Exception as exc:
            raise GraphDBClientError("GraphDB health response is not JSON") from exc
        return {
            "status": status,
            "healthy": 200 <= status < 300 and isinstance(value, list),
            "repository_count": len(value) if isinstance(value, list) else None,
        }

    def version_discovery(self) -> dict[str, Any]:
        import re

        status, body, headers = self._request(
            "GET", "/protocol", accept="text/plain"
        )
        server = next(
            (value for key, value in headers.items() if key.lower() == "server"),
            "",
        )
        match = re.search(r"GraphDB/([0-9]+(?:\.[0-9]+)+)", server)
        if status < 300 and match:
            return {
                "status": status,
                "path": "/protocol",
                "response": {
                    "productName": "GraphDB",
                    "productVersion": match.group(1),
                    "rdf4jProtocolVersion": body.decode("utf-8").strip(),
                },
            }
        for path in ("/rest/monitor/version", "/rest/info", "/protocol"):
            try:
                status, body, _ = self._request("GET", path, accept="application/json,text/plain")
                if status < 300:
                    try:
                        value = json.loads(body.decode("utf-8"), object_pairs_hook=unique_json)
                    except Exception:
                        value = {"raw": body.decode("utf-8", errors="replace")[:4096]}
                    return {"status": status, "path": path, "response": value}
            except GraphDBClientError:
                continue
        raise GraphDBClientError("GraphDB version endpoint unavailable")

    @staticmethod
    def _license_fields(value: Any) -> tuple[str | None, str]:
        observed_states: list[str] = []
        edition = "UNKNOWN"

        def walk(item: Any) -> None:
            nonlocal edition
            if isinstance(item, Mapping):
                for key, child in item.items():
                    normalized = str(key).lower().replace("_", "")
                    if normalized in {
                        "edition",
                        "licensetype",
                        "productedition",
                        "producttype",
                    } and isinstance(child, str):
                        upper = child.upper()
                        if upper in {"FREE", "ENTERPRISE"}:
                            edition = upper
                    if normalized in {"status", "state", "licensestatus", "licenseaccepted", "valid", "active"}:
                        if isinstance(child, bool):
                            observed_states.append("ACCEPTED" if child else "REJECTED")
                        elif isinstance(child, str):
                            upper = child.upper()
                            if upper in {"ACCEPTED", "VALID", "ACTIVE", "OK"}:
                                observed_states.append("ACCEPTED")
                            elif upper in {"REJECTED", "INVALID", "EXPIRED", "MISSING"}:
                                observed_states.append("REJECTED")
                    if normalized == "present" and child is False:
                        observed_states.append("REJECTED")
                    walk(child)
            elif isinstance(item, list):
                for child in item:
                    walk(child)

        walk(value)
        state = (
            "REJECTED"
            if "REJECTED" in observed_states
            else "ACCEPTED"
            if "ACCEPTED" in observed_states
            else None
        )
        return state, edition

    def license_discovery(self) -> dict[str, Any]:
        """Return only sanitized license readiness fields, never raw license data."""

        # GraphDB 11.4.2's shipped Workbench API declares the first endpoint.
        # Older diagnostic endpoints remain read-only fallbacks.
        for path in (
            "/rest/graphdb-settings/license",
            "/rest/monitor/license",
            "/rest/info",
        ):
            try:
                status, body, _ = self._request(
                    "GET", path, accept="application/json"
                )
            except GraphDBClientError:
                continue
            if status >= 300:
                continue
            try:
                value = json.loads(body.decode("utf-8"), object_pairs_hook=unique_json)
            except Exception:
                continue
            state, edition = self._license_fields(value)
            if state is not None:
                return {
                    "status": status,
                    "path": path,
                    "license_state": state,
                    "edition": edition,
                }
        raise GraphDBClientError("GraphDB license acceptance endpoint unavailable")

    def verify_runtime_readiness(self, *, expected_product_version: str) -> dict[str, Any]:
        health = self.health_check()
        if not health.get("healthy"):
            raise GraphDBClientError("GraphDB HTTP server is not healthy")
        version = self.version_discovery()
        response = version.get("response", {})
        if not isinstance(response, Mapping) or response.get("productName") != "GraphDB":
            raise GraphDBClientError("GraphDB product identity is unavailable")
        if response.get("productVersion") != expected_product_version:
            raise GraphDBClientError(
                f"GraphDB product version mismatch: expected {expected_product_version}"
            )
        license_info = self.license_discovery()
        if license_info.get("license_state") != "ACCEPTED":
            raise GraphDBClientError("GraphDB license was not accepted")
        # This proves repository operations are available under the accepted
        # license without creating or mutating a repository.
        repositories = self.list_repositories()
        return {
            "server_healthy": True,
            "product_version": response.get("productVersion"),
            "version": version,
            "license_state": "ACCEPTED",
            "edition": license_info.get("edition", "UNKNOWN"),
            "repository_operations": True,
            "repository_count": len(repositories),
        }

    def list_repositories(self) -> list[str]:
        status, body, _ = self._request("GET", "/rest/repositories", accept="application/json")
        if status >= 300:
            raise GraphDBClientError(f"unexpected repository list status: {status}")
        try:
            value = json.loads(body.decode("utf-8"), object_pairs_hook=unique_json)
        except Exception as exc:
            raise GraphDBClientError("repository list response is not JSON") from exc
        if not isinstance(value, list):
            raise GraphDBClientError("repository list response must be an array")
        result = []
        for item in value:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, Mapping) and isinstance(item.get("id"), str):
                result.append(item["id"])
        return sorted(set(result))

    def create_repository(self, config_ttl: bytes) -> int:
        boundary = "kgmnpstage07boundary"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"config\"; filename=\"repository-config.ttl\"\r\nContent-Type: text/turtle\r\n\r\n".encode("ascii") + config_ttl + f"\r\n--{boundary}--\r\n".encode("ascii"))
        status, _, _ = self._request("POST", "/rest/repositories", body=body, content_type=f"multipart/form-data; boundary={boundary}", accept="application/json,text/plain")
        if not 200 <= status < 300:
            raise GraphDBClientError(f"repository creation failed with status {status}")
        return status

    def inspect_repository(self, repository_id: str) -> dict[str, Any]:
        validate_repository_id(repository_id)
        path = "/rest/repositories/" + quote(repository_id, safe="")
        status, body, _ = self._request("GET", path, accept="application/json")
        if status >= 300:
            raise GraphDBClientError(f"repository inspection failed with status {status}")
        try:
            value = json.loads(body.decode("utf-8"), object_pairs_hook=unique_json)
        except Exception as exc:
            raise GraphDBClientError("repository inspection response is not JSON") from exc
        return value if isinstance(value, dict) else {"response": value}

    def count_repository_statements(self, repository_id: str) -> int:
        validate_repository_id(repository_id)
        status, body, _ = self._request("GET", "/repositories/" + quote(repository_id, safe="") + "/size", accept="text/plain,application/json")
        if status >= 300:
            raise GraphDBClientError(f"repository count failed with status {status}")
        raw = body.decode("utf-8").strip()
        try:
            return int(raw)
        except ValueError:
            try:
                value = json.loads(raw, object_pairs_hook=unique_json)
                return int(value.get("count", value.get("size")))
            except Exception as exc:
                raise GraphDBClientError("repository count response is invalid") from exc

    def import_nquads(self, repository_id: str, data: bytes) -> int:
        validate_repository_id(repository_id)
        status, _, _ = self._request("POST", "/repositories/" + quote(repository_id, safe="") + "/statements", body=data, content_type="application/n-quads", accept="application/json,text/plain")
        if not 200 <= status < 300:
            raise GraphDBClientError(f"N-Quads import failed with status {status}")
        return status

    def get_default_graph(self, repository_id: str) -> DefaultGraphSnapshot:
        """Read only the physical default graph through RDF4J Graph Store."""

        validate_repository_id(repository_id)
        path = (
            "/repositories/"
            + quote(repository_id, safe="")
            + "/rdf-graphs/service?default"
        )
        status, body, headers = self._request(
            "GET", path, accept="application/n-triples"
        )
        if not 200 <= status < 300:
            raise GraphDBClientError(
                f"default graph Graph Store read failed with status {status}"
            )
        graph = Graph()
        try:
            graph.parse(data=body.decode("utf-8"), format="nt")
        except Exception as exc:
            raise GraphDBClientError(
                "default graph Graph Store response is not valid N-Triples"
            ) from exc
        if any(isinstance(term, BNode) for triple in graph for term in triple):
            raise GraphDBClientError("default graph contains a blank node")
        canonical = canonical_ntriples(graph)
        content_type = next(
            (
                str(value).split(";", 1)[0].strip().lower()
                for key, value in headers.items()
                if key.lower() == "content-type"
            ),
            "",
        )
        return DefaultGraphSnapshot(
            http_status=status,
            statement_count=len(graph),
            semantic_hash=hashlib.sha256(canonical).hexdigest(),
            content_type=content_type,
        )

    def count_default_graph_statements(self, repository_id: str) -> int:
        return self.get_default_graph(repository_id).statement_count

    def assert_default_graph_empty(
        self, repository_id: str
    ) -> DefaultGraphSnapshot:
        snapshot = self.get_default_graph(repository_id)
        if snapshot.statement_count != 0:
            raise GraphDBClientError(
                "physical default graph is not empty: "
                f"{snapshot.statement_count} statement(s)"
            )
        return snapshot

    def replace_graph(
        self,
        repository_id: str,
        data: bytes,
        *,
        graph_iri: str | None = None,
        default: bool = False,
    ) -> int:
        """Replace a local test graph through Graph Store Protocol."""

        validate_repository_id(repository_id)
        if default == (graph_iri is not None):
            raise GraphDBClientError("choose exactly one of default or graph_iri")
        if default:
            suffix = "default"
        else:
            suffix = "graph=" + quote(str(graph_iri), safe="")
        path = (
            "/repositories/"
            + quote(repository_id, safe="")
            + "/rdf-graphs/service?"
            + suffix
        )
        status, _, _ = self._request(
            "PUT",
            path,
            body=data,
            content_type="application/n-triples",
            accept="application/json,text/plain",
        )
        if not 200 <= status < 300:
            raise GraphDBClientError(f"Graph Store graph replacement failed with status {status}")
        return status

    def sparql_select(self, repository_id: str, query: str) -> dict[str, Any]:
        return self._sparql(repository_id, query, ask=False)

    def sparql_ask(self, repository_id: str, query: str) -> bool:
        value = self._sparql(repository_id, query, ask=True)
        return bool(value.get("boolean"))

    def _sparql(self, repository_id: str, query: str, *, ask: bool) -> dict[str, Any]:
        validate_repository_id(repository_id)
        path = "/repositories/" + quote(repository_id, safe="")
        body = query.encode("utf-8")
        status, response, _ = self._request("POST", path, body=body, content_type="application/sparql-query", accept="application/sparql-results+json")
        if status >= 300:
            raise GraphDBClientError(f"SPARQL request failed with status {status}")
        try:
            value = json.loads(response.decode("utf-8"), object_pairs_hook=unique_json)
        except Exception as exc:
            raise GraphDBClientError("SPARQL response is not JSON") from exc
        if not isinstance(value, dict) or (ask and "boolean" not in value) or (not ask and "results" not in value):
            raise GraphDBClientError("malformed SPARQL result")
        return value

    def export_nquads(self, repository_id: str, *, include_inferred: bool = False) -> bytes:
        validate_repository_id(repository_id)
        status, body, _ = self._request(
            "GET",
            "/repositories/" + quote(repository_id, safe="") + "/statements?"
            + urlencode({"infer": "true" if include_inferred else "false"}),
            accept="application/n-quads",
        )
        if status >= 300:
            raise GraphDBClientError(f"explicit N-Quads export failed with status {status}")
        return body

    def delete_generated_repository(self, repository_id: str) -> int:
        validate_repository_id(repository_id)
        status, _, _ = self._request("DELETE", "/rest/repositories/" + quote(repository_id, safe=""), accept="application/json,text/plain")
        if not 200 <= status < 300:
            raise GraphDBClientError(f"repository deletion failed with status {status}")
        return status
