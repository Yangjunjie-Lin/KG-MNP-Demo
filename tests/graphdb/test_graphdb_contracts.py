from kg_mnp_demo.graphdb.attestation import build_import_attestation
from kg_mnp_demo.graphdb.contracts import graphdb_contract_names, load_graphdb_schema, validate_graphdb_contract
from kg_mnp_demo.graphdb.policy import load_graphdb_policy


def test_graphdb_contract_registry_is_closed_and_draft_2020_12():
    assert len(graphdb_contract_names()) == 7
    ids = []
    for name in graphdb_contract_names():
        schema = load_graphdb_schema(name)
        assert schema["$schema"].endswith("2020-12/schema")
        ids.append(schema["$id"])
    assert len(ids) == len(set(ids))


def test_runtime_policy_contract():
    validate_graphdb_contract("graphdb-runtime-policy", load_graphdb_policy())


def test_import_attestation_exposes_all_three_semantic_hashes():
    semantic_hash = "a" * 64
    query_results = {
        f"{index:02d}-check": {"boolean": True}
        for index in range(1, 10)
    }
    invariant_results = {
        f"{index:02d}-check": {"expected": True, "actual": True}
        for index in range(1, 4)
    }
    verification = {
        "status": "IMPORT_VERIFIED",
        "repository_id": "kg-mnp-" + "b" * 20,
        "actual_quad_count": 0,
        "expected_quad_count": 0,
        "expected_graph_counts": {},
        "actual_graph_counts": {},
        "default_graph_statement_count": 0,
        "default_graph_check": {
            "verification_type": "GRAPH_STORE_DEFAULT_GRAPH",
            "method": "GET /repositories/<repository-id>/rdf-graphs/service?default",
            "http_status": 200,
            "statement_count": 0,
            "semantic_hash": semantic_hash,
            "content_type": "application/n-triples",
        },
        "forbidden_assertion_count": 0,
        "violating_forbidden_assertion_count": 0,
        "inferred_statement_count": 0,
        "import_semantic_hash": semantic_hash,
        "export_semantic_hash": semantic_hash,
        "complete_export_semantic_hash": semantic_hash,
        "query_results": query_results,
        "invariant_results": invariant_results,
    }
    attestation = build_import_attestation(
        source_publication_id="urn:kg-mnp:graphdb-publication:" + "c" * 64,
        source_compilation_id="urn:kg-mnp:compilation:test",
        repository_config_hash="d" * 64,
        import_dataset_hash=semantic_hash,
        export_dataset_hash=semantic_hash,
        expected_graph_count=0,
        actual_graph_count=0,
        expected_quad_count=0,
        actual_quad_count=0,
        verification=verification,
        graphdb_version={
            "status": 200,
            "path": "/protocol",
            "response": {
                "productName": "GraphDB",
                "productVersion": "11.4.2",
                "rdf4jProtocolVersion": "12",
            },
        },
        image_digest="sha256:" + "e" * 64,
        repository_id="kg-mnp-" + "b" * 20,
        create_status=201,
        import_status=204,
        license_state="ACCEPTED",
        license_edition="ENTERPRISE",
        license_source_type="FILE",
    )

    assert attestation["import_semantic_hash"] == semantic_hash
    assert attestation["explicit_export_semantic_hash"] == semantic_hash
    assert attestation["complete_export_semantic_hash"] == semantic_hash
