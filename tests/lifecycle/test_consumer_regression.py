"""Nonempty real package queries, explicit Oracles and fail-closed contracts."""
import pytest

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.lifecycle.consumer import register_consumer
from kg_mnp.lifecycle.guards import package_record
from kg_mnp.lifecycle.registry.import_package import import_package
from kg_mnp.lifecycle.registry.manifest import init_registry
from kg_mnp.lifecycle.regression import plan_regression, run_regression


@pytest.fixture
def registered(prompt05_case, tmp_path):
    init_registry(tmp_path)
    record = import_package(tmp_path, prompt05_case["result"].package_directory,
        source_project_lock=prompt05_case["workspace"] / "project.lock.json")
    return tmp_path, package_record(tmp_path, record["package_id"])


def oracle(value=True):
    return {"assertion_type": "BOOLEAN_EQUALS", "boolean_value": value,
            "integer_value": None, "string_values": [], "semantic_hash": None}


def query(value=True):
    return {"query_id": stable_urn("consumer-query", {"value": value}),
            "query_type": "ASK", "query_text": "ASK { ?s ?p ?o }",
            "target_graph_roles": ["abox"], "assertions": [oracle(value)],
            "resource_limits": {"max_query_characters": 1000, "max_query_results": 100,
                                "max_query_seconds": 30, "max_query_path_depth": 4}}


def run(registered, category, **extra):
    root, record = registered
    plan = plan_regression(root, base_package_id=record["package_id"],
        candidate_package_id=record["package_id"], tests=[{
            "test_category": category, "expected_result": oracle(), **extra}])
    return run_regression(root, plan)


def test_consumer_query_runs_nonempty_dataset_and_actual_oracle(registered):
    root, record = registered
    for value in [True, False]:
        contract = register_consumer(root, consumer_name="positive" if value else "negative",
            ontology_iri=record["ontology_iri"], query_contracts=[query(value)])
        report = run(registered, "CONSUMER_QUERY", consumer_ref=contract["consumer_id"],
                     source_artifact_ref=query(value)["query_id"])
        assert report["required_passed"] is value
        assert report["tests"][0]["status"] == ("PASSED" if value else "FAILED")


def test_term_contract_checks_actual_iri_not_directory_presence(registered):
    report = run(registered, "TERM_CONTRACT", affected_iris=["urn:synthetic:missing-term"])
    assert report["required_passed"] is False


def test_incompatible_version_report_is_not_a_passing_boolean(registered):
    from kg_mnp.lifecycle.diff.versioning import check_version
    from kg_mnp.lifecycle.store import save
    root, record = registered
    version = check_version("1.0.0", "1.0.1", "BREAKING", registry_id=record["registry_id"])
    save(root, "records/version-compatibility/failing.json", version)
    report = run(registered, "VERSION_COMPATIBILITY", source_artifact_ref=version["report_id"])
    assert report["required_passed"] is False


def test_new_registered_consumer_invalidates_old_regression_coverage(registered):
    from kg_mnp.lifecycle.errors import LifecycleError
    from kg_mnp.lifecycle.regression import (
        declared_consumer_tests,
        require_consumer_coverage,
    )
    root, record = registered
    old = plan_regression(root, base_package_id=record["package_id"], candidate_package_id=record["package_id"])
    register_consumer(root, consumer_name="new-consumer", ontology_iri=record["ontology_iri"], query_contracts=[query()])
    with pytest.raises(LifecycleError, match="missing from regression"):
        require_consumer_coverage(root, old)
    plan = plan_regression(root, base_package_id=record["package_id"], candidate_package_id=record["package_id"],
                           tests=declared_consumer_tests(root, record["package_id"]))
    require_consumer_coverage(root, plan)
    assert run_regression(root, plan)["required_passed"] is True
