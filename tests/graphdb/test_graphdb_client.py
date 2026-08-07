import json

import pytest

from kg_mnp_demo.graphdb.client import GraphDBClient, GraphDBClientError, redact_credentials
from kg_mnp_demo.graphdb.identifiers import GraphDBIdentifierError


def test_remote_hosts_require_explicit_permission():
    with pytest.raises(GraphDBClientError):
        GraphDBClient("https://graphdb.example.com")
    assert GraphDBClient("https://graphdb.example.com", allow_remote=True).allow_remote


def test_repository_path_injection_is_rejected():
    client = GraphDBClient()
    with pytest.raises(GraphDBIdentifierError):
        client.count_repository_statements("../../admin")


def test_credential_redaction_removes_userinfo_and_query_tokens():
    value = redact_credentials("https://alice:secret@example.invalid:8443/repositories/x?token=hidden")
    assert value == "https://example.invalid:8443/repositories/x"
    assert "secret" not in value and "hidden" not in value
    with pytest.raises(GraphDBClientError):
        GraphDBClient("https://alice:secret@example.invalid", allow_remote=True)


def test_license_discovery_uses_graphdb_1142_settings_endpoint(monkeypatch):
    client = GraphDBClient()
    requested_paths = []

    def request(method, path, **kwargs):
        requested_paths.append(path)
        if path != "/rest/graphdb-settings/license":
            raise GraphDBClientError("unexpected endpoint")
        return (
            200,
            json.dumps(
                {
                    "present": True,
                    "valid": True,
                    "productType": "ENTERPRISE",
                    "licensee": "must-not-be-returned",
                    "installationId": "must-not-be-returned",
                }
            ).encode("utf-8"),
            {"Content-Type": "application/json"},
        )

    monkeypatch.setattr(client, "_request", request)

    assert client.license_discovery() == {
        "status": 200,
        "path": "/rest/graphdb-settings/license",
        "license_state": "ACCEPTED",
        "edition": "ENTERPRISE",
    }
    assert requested_paths == ["/rest/graphdb-settings/license"]
