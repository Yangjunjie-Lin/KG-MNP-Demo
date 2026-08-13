from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import kg_mnp_demo.governance as governance_api
import scripts.governance_controlled_fixture as controlled_fixture_module
from kg_mnp_demo.governance.authority_binding import GovernanceAuthority
from kg_mnp_demo.governance.errors import GovernanceError, GovernanceErrorCode
from kg_mnp_demo.governance.workspace import GovernanceWorkspace
from scripts.governance_controlled_fixture import (
    FIXTURE_NAMESPACE,
    FIXTURE_STATUS,
    FIXTURE_TYPE,
    ControlledDiagnosticFixture,
    controlled_governance_authority_for_test_harness,
)


def _caller_authored_iris(value, field: str | None = None):
    fields = {
        "publication_id",
        "focus_node",
        "path",
        "authority_iri",
        "shape_iri",
        "constraint_iri",
        "assertion_ref",
        "candidate_ref",
        "review_decision_ref",
    }
    if field in fields and value is not None:
        yield value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _caller_authored_iris(child, key)
    elif isinstance(value, list):
        for child in value:
            yield from _caller_authored_iris(child, field)


def _all_urns(value):
    if isinstance(value, str) and value.startswith("urn:"):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _all_urns(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_urns(child)


def test_controlled_diagnostics_are_explicitly_test_only() -> None:
    fixture = ControlledDiagnosticFixture.create()
    document = fixture.to_dict()
    assert document["fixture_type"] == FIXTURE_TYPE
    assert document["status"] == FIXTURE_STATUS
    assert document["production_authority"] is False
    assert document["test_only"] is True
    assert document["fixture_id"].startswith(FIXTURE_NAMESPACE)
    assert len(document["controlled_fixture_hash"]) == 64
    assert (
        document["controlled_fixture_diagnostic_package_hash"]
        == document["diagnostic_package"]["manifest"][
            "controlled_fixture_diagnostic_package_hash"
        ]
    )
    assert "package_semantic_hash" not in document["diagnostic_package"]["manifest"]
    assert "attestation" not in document
    assert "APPLICATION_DIAGNOSTICS_VERIFIED" not in repr(document)
    assert "build_application_phase03_attestation" not in inspect.getsource(
        controlled_fixture_module
    )


def test_controlled_fixture_is_deterministic_and_uses_test_namespace() -> None:
    first = ControlledDiagnosticFixture.create()
    second = ControlledDiagnosticFixture.create()
    assert first.to_dict() == second.to_dict()
    assert first.controlled_fixture_hash == second.controlled_fixture_hash
    assert first.controlled_fixture_diagnostic_package_hash == (
        second.controlled_fixture_diagnostic_package_hash
    )
    assert first.diagnostic_package["summary"]["issues_total"] == 4
    iris = list(_caller_authored_iris(first.authority_snapshot))
    assert iris
    assert all(value.startswith(FIXTURE_NAMESPACE) for value in iris)
    all_fixture_iris = list(_all_urns(first.to_dict()))
    assert all_fixture_iris
    assert all(value.startswith(FIXTURE_NAMESPACE) for value in all_fixture_iris)


def test_fixture_only_enters_governance_through_named_test_adapter() -> None:
    fixture = ControlledDiagnosticFixture.create()
    assert not isinstance(fixture, GovernanceAuthority)
    with pytest.raises((AttributeError, TypeError)):
        GovernanceWorkspace.initialize(fixture)  # type: ignore[arg-type]
    authority = controlled_governance_authority_for_test_harness(fixture)
    assert authority.authority_type == "CONTROLLED_TEST_HARNESS"
    assert authority.publication_id.startswith(FIXTURE_NAMESPACE)
    assert (
        authority.upstream_phase03_diagnostic_package_hash
        == fixture.controlled_fixture_diagnostic_package_hash
    )
    assert len(authority.issues) == 4
    workspace = GovernanceWorkspace.initialize(authority)
    assert workspace.value["workspace_revision"] == 0
    assert workspace.value["events"] == []


def test_fixture_cannot_construct_a_production_governance_authority() -> None:
    fixture = ControlledDiagnosticFixture.create()
    controlled = controlled_governance_authority_for_test_harness(fixture)
    with pytest.raises(GovernanceError) as caught:
        GovernanceAuthority(
            authority_type="PRODUCTION_EXACT_PHASE03",
            publication_id=controlled.publication_id,
            publication_semantic_hash=controlled.publication_semantic_hash,
            repository_semantic_hash=controlled.repository_semantic_hash,
            upstream_phase03_attestation_sha256=(
                controlled.upstream_phase03_attestation_sha256
            ),
            upstream_phase03_diagnostic_package_hash=(
                controlled.upstream_phase03_diagnostic_package_hash
            ),
            issues=controlled.issues,
        )
    assert caught.value.code == GovernanceErrorCode.AUTHORITY_MISMATCH


def test_production_loader_has_no_caller_injected_authority_inputs() -> None:
    loader = governance_api.load_production_phase03_authority
    parameters = set(inspect.signature(loader).parameters)
    assert not {
        "authority_snapshot",
        "diagnostic_package",
        "phase03_attestation",
        "authority",
    } & parameters
    assert not hasattr(governance_api, "load_verified_phase03_authority")


def test_phase04_rejects_controlled_fixture_as_production_authority() -> None:
    fixture = ControlledDiagnosticFixture.create()
    with pytest.raises(GovernanceError) as caught:
        governance_api.load_production_phase03_authority(
            publication_package_directory=Path("unreached-publication-package"),
            publication_attestation_path=Path("unreached-publication-attestation.json"),
            phase01_artifact_directory=Path("unreached-phase01-artifact"),
            phase02_artifact_directory=Path("unreached-phase02-artifact"),
            phase03_artifact_directory=fixture,
            expected_commit_sha="1" * 40,
        )
    assert (
        caught.value.code
        == GovernanceErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY
    )


@pytest.mark.parametrize(
    "forbidden_argument",
    ["authority_snapshot", "diagnostic_package", "phase03_attestation", "authority"],
)
def test_synthetic_authority_injection_is_not_a_production_api(
    forbidden_argument: str,
) -> None:
    fixture = ControlledDiagnosticFixture.create()
    attack = {
        # A fully self-consistent controlled package remains untrusted regardless
        # of copied identifiers and attacker-controlled rehashing.
        forbidden_argument: (
            fixture.authority_snapshot
            if forbidden_argument == "authority_snapshot"
            else fixture.diagnostic_package
        )
    }
    with pytest.raises(TypeError, match=forbidden_argument):
        governance_api.load_production_phase03_authority(
            publication_package_directory=Path("publication-package"),
            publication_attestation_path=Path("publication-attestation.json"),
            phase01_artifact_directory=Path("phase01-artifact"),
            phase02_artifact_directory=Path("phase02-artifact"),
            phase03_artifact_directory=Path("phase03-artifact"),
            expected_commit_sha="1" * 40,
            **attack,
        )
