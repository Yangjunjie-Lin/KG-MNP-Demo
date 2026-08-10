from __future__ import annotations

from kg_mnp_demo.workbench.policy import (
    ALLOWED_PHASE01_ROUTES,
    load_workbench_policy,
    workbench_policy_hash,
)


def test_runtime_policy_is_loopback_read_only_and_phase01_only() -> None:
    policy = load_workbench_policy()
    assert policy["network"] == {
        "bind_host": "127.0.0.1",
        "default_port": 8092,
        "external_exposure": "FORBIDDEN",
        "runtime_internet_access": "FORBIDDEN",
        "browser_same_origin_only": "REQUIRED",
    }
    assert policy["relay"]["phase01_api_only"] == "REQUIRED"
    assert policy["relay"]["arbitrary_targets"] == "FORBIDDEN"
    assert tuple(policy["relay"]["allowed_routes"]) == ALLOWED_PHASE01_ROUTES
    assert set(policy["authority"].values()) == {"FORBIDDEN"}
    assert policy["presentation"]["rdf_text_rendering"] == "TEXT_ONLY"
    assert len(workbench_policy_hash()) == 64
