from __future__ import annotations

from fastapi.testclient import TestClient

from kg_mnp_demo.workbench.binding import WorkbenchBinding
from kg_mnp_demo.workbench.runtime import CSP, create_workbench_app

from ._helpers import ENTITY, FakeRelay, write_phase01_artifact


def client(tmp_path):
    binding = WorkbenchBinding.load(write_phase01_artifact(tmp_path / "phase01"))
    return TestClient(
        create_workbench_app(binding=binding, relay=FakeRelay(binding)),
        raise_server_exceptions=False,
    )


def test_pages_assets_status_and_csp_are_same_origin_read_only(tmp_path) -> None:
    with client(tmp_path) as http:
        for path in ("/", "/ontology", "/entity", "/fact", "/trace", "/review"):
            response = http.get(path)
            assert response.status_code == 200
            assert response.headers["content-security-policy"] == CSP
            assert response.headers["cache-control"] == "no-store, max-age=0"
        assert http.get("/assets/app.js").status_code == 200
        assert http.get("/assets/styles.css").status_code == 200
        status = http.get("/workbench/api/status")
        assert status.status_code == 200
        assert status.json()["status"] == "WORKBENCH_READY"
        assert status.json()["ontology_version"].endswith("mnp-evidence-time")


def test_all_view_routes_return_deterministic_view_models(tmp_path) -> None:
    requests = (
        ("/workbench/api/view/ontology/classes", {}),
        ("/workbench/api/view/ontology/properties", {}),
        ("/workbench/api/view/ontology/term", {"iri": "urn:term"}),
        ("/workbench/api/view/entity", {"iri": ENTITY}),
        (
            "/workbench/api/view/fact",
            {
                "subject": ENTITY,
                "predicate": "urn:kg-mnp:predicate:test",
                "object_type": "LITERAL",
                "object_value": "ACTIVE",
                "datatype_iri": "urn:datatype:test",
            },
        ),
        (
            "/workbench/api/view/fact/provenance",
            {
                "subject": ENTITY,
                "predicate": "urn:kg-mnp:predicate:test",
                "object_type": "LITERAL",
                "object_value": "ACTIVE",
                "datatype_iri": "urn:datatype:test",
            },
        ),
        ("/workbench/api/view/review", {"resource_id": "urn:candidate"}),
        ("/workbench/api/view/source", {"source_ref": "urn:source"}),
        ("/workbench/api/view/evidence", {"evidence_ref": "urn:evidence"}),
        ("/workbench/api/view/trace", {"resource_id": "urn:resource"}),
    )
    with client(tmp_path) as http:
        for path, parameters in requests:
            first = http.get(path, params=parameters)
            second = http.get(path, params=parameters)
            assert first.status_code == second.status_code == 200
            assert first.json() == second.json()
            assert first.json()["source_result_hash"] == "a" * 64


def test_mutations_bodies_unknown_routes_and_invalid_inputs_fail_closed(tmp_path) -> None:
    with client(tmp_path) as http:
        for method in ("POST", "PUT", "PATCH", "DELETE", "CONNECT"):
            response = http.request(method, "/workbench/api/status", content=b"attack")
            assert response.status_code == 405
            assert response.json()["error"]["code"] == "READ_ONLY_POLICY_VIOLATION"
        assert http.get("/proxy/http://evil.example").status_code == 404
        assert http.get("/workbench/api/view/entity", params={"iri": "x" * 3000}).status_code == 422
        assert http.request("GET", "/", content=b"body").status_code == 405
