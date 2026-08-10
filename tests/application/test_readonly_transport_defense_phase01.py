from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.request import ProxyHandler

import pytest

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.query_validator import assert_readonly_http_request
from kg_mnp_demo.application.readonly_client import (
    ReadOnlyGraphDBClient,
    _NoRedirectHandler,
)


REPOSITORY_ID = "kg-mnp-" + "0" * 20


def test_low_level_sparql_query_transport_rejects_insert_body():
    client = ReadOnlyGraphDBClient()

    with pytest.raises(ApplicationError) as caught:
        client._request(
            "POST",
            f"/repositories/{REPOSITORY_ID}?timeout=5",
            body=b"INSERT DATA { <urn:s> <urn:p> <urn:o> }",
            content_type="application/sparql-query",
            accept="application/sparql-results+json",
        )

    assert caught.value.code == ErrorCode.READ_ONLY_POLICY_VIOLATION


@pytest.mark.parametrize(
    "query",
    [
        "DELETE WHERE { GRAPH ?g { ?s ?p ?o } }",
        "CLEAR ALL",
        "DROP GRAPH <urn:g>",
        "CREATE GRAPH <urn:g>",
        "LOAD <urn:source> INTO GRAPH <urn:g>",
        "MOVE GRAPH <urn:a> TO GRAPH <urn:b>",
        "COPY GRAPH <urn:a> TO GRAPH <urn:b>",
        "ADD GRAPH <urn:a> TO GRAPH <urn:b>",
        "SELECT * WHERE { SERVICE <https://example.invalid/sparql> { ?s ?p ?o } GRAPH ?g { ?s ?p ?o } }",
        "WITH <urn:g> DELETE { ?s ?p ?o } WHERE { ?s ?p ?o }",
        "DELETE { ?s ?p ?o } USING <urn:g> WHERE { ?s ?p ?o }",
    ],
)
def test_low_level_sparql_transport_rejects_every_update_or_remote_token(query: str):
    with pytest.raises(ApplicationError) as caught:
        assert_readonly_http_request(
            "POST",
            f"/repositories/{REPOSITORY_ID}?timeout=5",
            "application/sparql-query",
            body=query.encode("utf-8"),
            accept="application/sparql-results+json",
        )
    assert caught.value.code == ErrorCode.READ_ONLY_POLICY_VIOLATION


@pytest.mark.parametrize(
    "target",
    [
        f"/repositories/{REPOSITORY_ID}/statements?infer=true",
        f"/repositories/{REPOSITORY_ID}/statements?infer=false&limit=1",
        f"/repositories/{REPOSITORY_ID}/statements",
        f"/repositories/{REPOSITORY_ID}/statements?infer=false#fragment",
        f"/repositories/{REPOSITORY_ID}/statements/extra?infer=false",
    ],
)
def test_explicit_snapshot_transport_requires_exact_infer_false_target(target: str):
    with pytest.raises(ApplicationError) as caught:
        assert_readonly_http_request("GET", target, None)
    assert caught.value.code == ErrorCode.READ_ONLY_POLICY_VIOLATION


def test_explicit_snapshot_transport_requires_nquads_accept_header():
    with pytest.raises(ApplicationError) as caught:
        assert_readonly_http_request(
            "GET",
            f"/repositories/{REPOSITORY_ID}/statements?infer=false",
            None,
            accept="text/turtle",
        )
    assert caught.value.code == ErrorCode.READ_ONLY_POLICY_VIOLATION


def test_client_transport_disables_environment_proxies_and_redirects(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:65534")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:65534")
    client = ReadOnlyGraphDBClient()

    proxy_handlers = [
        handler
        for handler in client._opener.handlers
        if isinstance(handler, ProxyHandler)
    ]
    assert proxy_handlers == []
    assert sum(
        isinstance(handler, _NoRedirectHandler)
        for handler in client._opener.handlers
    ) == 1


def test_client_transport_does_not_follow_even_loopback_redirects():
    observed = {"redirect_target_hits": 0}

    class RedirectingHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/rest/repositories":
                self.send_response(302)
                self.send_header("Location", "/redirect-target")
                self.end_headers()
                return
            observed["redirect_target_hits"] += 1
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"[]")

        def log_message(self, _format, *_args):
            return

    with ThreadingHTTPServer(("127.0.0.1", 0), RedirectingHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            client = ReadOnlyGraphDBClient(f"http://{host}:{port}", timeout=1)
            with pytest.raises(ApplicationError) as caught:
                client.health()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    assert caught.value.code == ErrorCode.GRAPHDB_UNAVAILABLE
    assert observed["redirect_target_hits"] == 0


def test_export_explicit_nquads_uses_only_bounded_read_endpoint(monkeypatch):
    observed = {}

    class Response:
        status = 200
        headers = {"Content-Type": "application/n-quads; charset=UTF-8"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, limit):
            observed["limit"] = limit
            return b"<urn:s> <urn:p> <urn:o> <urn:g> .\n"

    class Opener:
        def open(self, request, *, timeout):
            observed["url"] = request.full_url
            observed["method"] = request.get_method()
            observed["accept"] = request.get_header("Accept")
            observed["timeout"] = timeout
            return Response()

    client = ReadOnlyGraphDBClient(timeout=4)
    monkeypatch.setattr(client, "_opener", Opener())

    result = client.export_explicit_nquads(REPOSITORY_ID)

    assert result == b"<urn:s> <urn:p> <urn:o> <urn:g> .\n"
    assert observed == {
        "url": f"http://127.0.0.1:7200/repositories/{REPOSITORY_ID}/statements?infer=false",
        "method": "GET",
        "accept": "application/n-quads",
        "timeout": 4.0,
        "limit": 2 * 1024 * 1024 + 1,
    }
