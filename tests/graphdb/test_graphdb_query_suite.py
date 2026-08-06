import pytest

from kg_mnp_demo.graphdb.query_suite import build_query_suite, query_suite_hash
from kg_mnp_demo.graphdb.contracts import GraphDBContractError, validate_graphdb_contract


def test_query_suite_has_ten_read_only_queries_and_stable_hash():
    stage06 = {"business_abox": "urn:b", "modeling_provenance": "urn:p", "review_audit": "urn:r"}
    suite = build_query_suite({"root": "urn:t"}, tbox_modules=1, expected_counts={"urn:t": 1, "urn:b": 1, "urn:p": 1, "urn:r": 1}, stage06_graphs=stage06)
    assert len(suite["queries"]) == 10
    assert suite["expected"]["named_graphs"] == ["urn:b", "urn:p", "urn:r", "urn:t"]
    assert query_suite_hash(suite) == suite["query_suite_hash"]
    forbidden = (" SERVICE ", " LOAD ", " INSERT ", " DELETE ", " CLEAR ", " DROP ", " CREATE ", " MOVE ", " COPY ", " ADD ")
    assert all(not any(word in (" " + query.upper() + " ") for word in forbidden) for query in suite["queries"].values())
    validate_graphdb_contract("query-suite-manifest", suite)


def test_query_suite_rejects_update_and_service_injection():
    stage06 = {"business_abox": "urn:b", "modeling_provenance": "urn:p", "review_audit": "urn:r"}
    suite = build_query_suite({"root": "urn:t"}, tbox_modules=1, expected_counts={"urn:t": 1, "urn:b": 1, "urn:p": 1, "urn:r": 1}, stage06_graphs=stage06)
    suite["queries"]["07-no-default-graph"] = "ASK { SERVICE <https://example.invalid> { ?s ?p ?o } }"
    suite["query_suite_hash"] = query_suite_hash(suite)
    suite["query_suite_id"] = "urn:kg-mnp:graphdb-query-suite:" + suite["query_suite_hash"]
    with pytest.raises(GraphDBContractError):
        validate_graphdb_contract("query-suite-manifest", suite)
