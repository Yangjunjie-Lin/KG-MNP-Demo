from kg_mnp_demo.graphdb.contracts import graphdb_contract_names, load_graphdb_schema, validate_graphdb_contract
from kg_mnp_demo.graphdb.policy import load_graphdb_policy


def test_graphdb_contract_registry_is_closed_and_draft_2020_12():
    assert len(graphdb_contract_names()) == 6
    ids = []
    for name in graphdb_contract_names():
        schema = load_graphdb_schema(name)
        assert schema["$schema"].endswith("2020-12/schema")
        ids.append(schema["$id"])
    assert len(ids) == len(set(ids))


def test_runtime_policy_contract():
    validate_graphdb_contract("graphdb-runtime-policy", load_graphdb_policy())
