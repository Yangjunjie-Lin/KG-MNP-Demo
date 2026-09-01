from __future__ import annotations

import copy

import pytest

from kg_mnp.semantic_kernel.contracts import verify_artifact
from kg_mnp.semantic_kernel.plan import build_compilation_plan


def test_plan_binds_every_candidate_limit_operation_and_explicit_identity(prompt05_case: dict) -> None:
    plan = prompt05_case["plan"]
    verify_artifact(plan, id_field="plan_id", urn_kind="semantic-compilation-plan", contract="semantic-compilation-plan")
    assert len(plan["candidate_dispatch"]) == 9
    assert {item["candidate_id"] for item in plan["candidate_dispatch"]} == {
        item["candidate_id"]
        for partition in ("confirmed_tbox", "confirmed_mapping", "confirmed_abox", "confirmed_shacl")
        for item in prompt05_case["prompt04"]["package"][partition]
    }
    assert len(plan["operations"]) == 17
    assert all(value > 0 for value in plan["resource_limits"].values())
    assert plan["package_identity"]["package_version"] == "0.1.0"
    assert plan["ontology_identity"]["version_iri"].endswith("/0.1.0")


@pytest.mark.parametrize(
    ("package_name", "package_version", "version_iri"),
    [
        ("Unsafe Name", "1.0.0", "https://example.test/ontology/1.0.0"),
        ("safe-name", "latest", "https://example.test/ontology/latest"),
        ("safe-name", "1.0.0", "https://example.test/ontology/2.0.0"),
    ],
)
def test_plan_rejects_implicit_or_inconsistent_identity(prompt05_case: dict, package_name: str, package_version: str, version_iri: str) -> None:
    source = prompt05_case["plan"]
    with pytest.raises(ValueError):
        build_compilation_plan(
            attestation=prompt05_case["attestation"],
            confirmed_package=prompt05_case["prompt04"]["package"],
            compiler_snapshot=prompt05_case["compiler"].snapshot,
            compiler_policy=prompt05_case["compiler"].policy,
            package_name=package_name,
            package_version=package_version,
            ontology_iri=source["ontology_identity"]["ontology_iri"],
            version_iri=version_iri,
            default_namespace=source["ontology_identity"]["default_namespace"],
            cq_test_plan=prompt05_case["cq_plan"],
        )


def test_plan_identity_changes_when_any_finite_resource_limit_changes(prompt05_case: dict) -> None:
    policy = copy.deepcopy(prompt05_case["compiler"].policy)
    policy["resource_limits"]["max_abox_statements"] += 1
    source = prompt05_case["plan"]
    changed = build_compilation_plan(
        attestation=prompt05_case["attestation"],
        confirmed_package=prompt05_case["prompt04"]["package"],
        compiler_snapshot=prompt05_case["compiler"].snapshot,
        compiler_policy=policy,
        package_name=source["package_identity"]["package_name"],
        package_version=source["package_identity"]["package_version"],
        ontology_iri=source["ontology_identity"]["ontology_iri"],
        version_iri=source["ontology_identity"]["version_iri"],
        default_namespace=source["ontology_identity"]["default_namespace"],
        cq_test_plan=prompt05_case["cq_plan"],
        baseline_assets=source["baseline_assets"],
        baseline_ontology_iris=source["ontology_identity"]["baseline_ontology_iris"],
    )
    assert changed["plan_id"] != source["plan_id"]
