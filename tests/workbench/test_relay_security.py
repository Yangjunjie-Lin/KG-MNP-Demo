from __future__ import annotations

import pytest

from kg_mnp_demo.workbench.binding import WorkbenchBinding
from kg_mnp_demo.workbench.errors import WorkbenchError
from kg_mnp_demo.workbench.relay import Phase01Relay

from ._helpers import write_phase01_artifact


@pytest.mark.parametrize(
    "path",
    [
        "http://evil.example/",
        "https://evil.example/",
        "//evil.example/",
        "/@evil.example",
        "/%68%74%74%70%3A%2F%2Fevil.example",
        "/%2568%2574%2574%2570%253A%252F%252Fevil.example",
        "/api/v1/../../secret",
        "/api/v1/entity?iri=http://evil.example",
        "/repositories/attacker",
        "\\\\evil.example\\share",
    ],
)
def test_absolute_encoded_and_non_allowlisted_targets_are_blocked(path) -> None:
    with pytest.raises(WorkbenchError):
        Phase01Relay.validate_request("GET", path, {})


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "CONNECT", "OPTIONS"])
def test_mutating_and_tunneling_methods_are_blocked(method) -> None:
    with pytest.raises(WorkbenchError, match="READ_ONLY_POLICY_VIOLATION"):
        Phase01Relay.validate_request(method, "/api/v1/health", {})


def test_query_parameter_allowlist_is_exact() -> None:
    Phase01Relay.validate_request(
        "GET",
        "/api/v1/entity",
        {"iri": "urn:test", "limit": 10, "offset": 0},
    )
    with pytest.raises(WorkbenchError, match="INVALID_REQUEST"):
        Phase01Relay.validate_request(
            "GET",
            "/api/v1/entity",
            {"iri": "urn:test", "target": "http://evil.example"},
        )


@pytest.mark.parametrize(
    "upstream",
    [
        "https://127.0.0.1:8081",
        "http://localhost:8081",
        "http://0.0.0.0:8081",
        "http://127.0.0.1:8081/api",
        "http://evil.example:8081",
        "http://user@127.0.0.1:8081",
    ],
)
def test_upstream_is_frozen_to_explicit_ipv4_loopback(tmp_path, upstream) -> None:
    binding = WorkbenchBinding.load(write_phase01_artifact(tmp_path / "phase01"))
    with pytest.raises(WorkbenchError, match="WORKBENCH_NOT_READY"):
        Phase01Relay(upstream, binding)
