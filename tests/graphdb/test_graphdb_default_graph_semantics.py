from __future__ import annotations

import pytest

from kg_mnp_demo.graphdb.client import GraphDBClient, GraphDBClientError
from kg_mnp_demo.graphdb.query_suite import build_query_suite


class _GraphStoreClient(GraphDBClient):
    def __init__(self, response: bytes):
        super().__init__()
        self.response = response

    def _request(self, method, path, **kwargs):
        assert method == "GET"
        assert path == "/repositories/kg-mnp-00000000000000000000/rdf-graphs/service?default"
        assert kwargs["accept"] == "application/n-triples"
        return 200, self.response, {"Content-Type": "application/n-triples"}


def _suite():
    stage06 = {
        "business_abox": "urn:b",
        "modeling_provenance": "urn:p",
        "review_audit": "urn:r",
    }
    return build_query_suite(
        {"root": "urn:t"},
        tbox_modules=1,
        expected_counts={"urn:t": 1, "urn:b": 1, "urn:p": 1, "urn:r": 1},
        stage06_graphs=stage06,
    )


def test_default_graph_is_a_graph_store_check_not_a_sparql_default_dataset_query():
    suite = _suite()

    assert "07-no-default-graph" not in suite["queries"]
    check = suite["verifications"]["07-default-graph-storage"]
    assert check == {
        "verification_type": "GRAPH_STORE_DEFAULT_GRAPH",
        "expected_statement_count": 0,
    }


def test_named_graph_union_visibility_does_not_change_physical_default_graph_count():
    # GraphDB can expose named-graph data to a plain ?s ?p ?o pattern through
    # its configured SPARQL default dataset.  Graph Store Protocol is the
    # independent physical default-graph storage check.
    ordinary_sparql_default_dataset_count = 1
    client = _GraphStoreClient(b"")

    snapshot = client.get_default_graph("kg-mnp-00000000000000000000")

    assert ordinary_sparql_default_dataset_count > 0
    assert snapshot.http_status == 200
    assert snapshot.statement_count == 0


def test_physical_default_graph_injection_is_detected():
    client = _GraphStoreClient(b"<urn:attack:s> <urn:attack:p> <urn:attack:o> .\n")

    snapshot = client.get_default_graph("kg-mnp-00000000000000000000")

    assert snapshot.statement_count == 1
    try:
        client.assert_default_graph_empty("kg-mnp-00000000000000000000")
    except Exception as exc:
        assert "default graph" in str(exc).lower()
    else:
        raise AssertionError("physical default graph injection was accepted")


@pytest.mark.parametrize(
    "response",
    [
        b"not valid N-Triples",
        b"_:blank <urn:p> <urn:o> .\n",
    ],
)
def test_default_graph_malformed_rdf_or_blank_nodes_fail_closed(response):
    with pytest.raises(GraphDBClientError):
        _GraphStoreClient(response).get_default_graph(
            "kg-mnp-00000000000000000000"
        )
