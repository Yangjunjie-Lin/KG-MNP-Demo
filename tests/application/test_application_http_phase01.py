from __future__ import annotations

from fastapi.testclient import TestClient

from kg_mnp_demo.application.http import create_app
from kg_mnp_demo.application.query_registry import QueryRegistry
from kg_mnp_demo.application.service import ApplicationService

from ._phase01_helpers import DatasetClient, synthetic_binding
from .test_application_queries_phase01 import STATUS, SUBSCRIPTION


def client():
    service = ApplicationService(binding=synthetic_binding(), registry=QueryRegistry.load(), client=DatasetClient())
    return TestClient(create_app(service), raise_server_exceptions=False)


def test_http_surface_is_local_read_only_and_has_no_arbitrary_sparql_route():
    with client() as http:
        assert http.get("/api/v1/health").status_code == 200
        assert "/sparql" not in http.get("/openapi.json").text.lower()
        response = http.post("/sparql", content="SELECT * WHERE { ?s ?p ?o }")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "READ_ONLY_POLICY_VIOLATION"


def test_http_entity_fact_provenance_unknown_entity_and_invalid_iri_contracts():
    with client() as http:
        entity = http.get("/api/v1/entity", params={"iri": SUBSCRIPTION})
        assert entity.status_code == 200
        provenance = http.get(
            "/api/v1/fact/provenance",
            params={
                "subject": SUBSCRIPTION,
                "predicate": STATUS,
                "object_type": "LITERAL",
                "object_value": "ACTIVE",
                "datatype_iri": "http://www.w3.org/2001/XMLSchema#string",
            },
        )
        assert provenance.status_code == 200
        assert provenance.json()["traceability"]["review"]
        unknown = http.get("/api/v1/entity", params={"iri": "urn:kg-mnp:unknown"})
        assert unknown.status_code == 200 and unknown.json()["result_count"] == 0
        invalid = http.get("/api/v1/entity", params={"iri": "file:///etc/passwd"})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "INVALID_IRI"


def test_encoded_path_traversal_double_encoding_and_request_body_fail_closed():
    with client() as http:
        for iri in ("https://yangjunjie-lin.github.io/KG-MNP-Demo/%2e%2e/secret", "https%253A%252F%252Fyangjunjie-lin.github.io%252FKG-MNP-Demo%252Fx"):
            response = http.get("/api/v1/entity", params={"iri": iri})
            assert response.status_code == 422
        response = http.request("GET", "/api/v1/health", content=b"unexpected")
        assert response.status_code == 405
        too_long = http.get("/api/v1/entity", params={"iri": "urn:kg-mnp:" + "x" * 3000})
        assert too_long.status_code == 422
        assert too_long.json()["error"]["code"] == "INVALID_PARAMETER"
