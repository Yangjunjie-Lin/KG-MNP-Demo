from __future__ import annotations

import pytest

from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.query_validator import assert_readonly_http_request
from kg_mnp_demo.application.readonly_client import ReadOnlyGraphDBClient


def test_public_client_surface_has_no_write_methods():
    client = ReadOnlyGraphDBClient()
    for name in ("create_repository", "delete_repository", "import_nquads", "replace_graph", "update", "graph_store"):
        assert not hasattr(client, name)
    assert {"health", "repository_info", "export_explicit_nquads", "select", "ask"} <= set(
        dir(client)
    )
    assert not hasattr(client, "construct")


@pytest.mark.parametrize(
    ("method", "path", "content_type"),
    [
        ("PUT", "/repositories/kg-mnp-" + "0" * 20 + "/rdf-graphs/service", "application/n-quads"),
        ("DELETE", "/rest/repositories/kg-mnp-" + "0" * 20, None),
        ("POST", "/repositories/kg-mnp-" + "0" * 20 + "/statements", "application/n-quads"),
        ("POST", "/repositories/kg-mnp-" + "0" * 20, "application/sparql-update"),
    ],
)
def test_transport_rejects_graph_store_repository_and_update_attacks(method, path, content_type):
    with pytest.raises(ApplicationError) as caught:
        assert_readonly_http_request(method, path, content_type)
    assert caught.value.code == ErrorCode.READ_ONLY_POLICY_VIOLATION


def test_client_rejects_non_loopback_graphdb():
    with pytest.raises(ApplicationError):
        ReadOnlyGraphDBClient("https://graphdb.example.com")
