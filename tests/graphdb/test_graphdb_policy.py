import copy
import pytest

from kg_mnp_demo.graphdb.policy import GraphDBPolicyError, load_graphdb_policy, validate_graphdb_policy


def test_policy_freezes_versions_digests_and_local_binding():
    policy = load_graphdb_policy()
    assert policy["graphdb"]["product_version"] == "11.4.2"
    assert policy["network"] == {"host": "127.0.0.1", "port": 7200, "external_exposure": "FORBIDDEN"}
    assert policy["repository"]["ruleset"] == "empty"


def test_non_empty_ruleset_fails_closed():
    policy = copy.deepcopy(load_graphdb_policy())
    policy["repository"]["ruleset"] = "owl2-rl"
    with pytest.raises(GraphDBPolicyError):
        validate_graphdb_policy(policy)
