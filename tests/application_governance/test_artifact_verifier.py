from __future__ import annotations

import copy
import inspect
from pathlib import Path

import pytest

import kg_mnp_demo.governance.artifact_verifier as verifier_module
from kg_mnp_demo.governance.artifact_verifier import (
    AUTHORITY_LAUNDERING_ATTACKS,
    AUTHORITY_LAUNDERING_OUTCOMES,
    FILES,
    Phase04ArtifactVerificationError,
    verify_application_phase04_artifact,
)
from kg_mnp_demo.governance.attestation import CATEGORY_FIELDS
from kg_mnp_demo.governance.workspace import GovernanceWorkspace
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash
from scripts.governance_controlled_fixture import ControlledDiagnosticFixture

from ._helpers import authority

COMMIT = "1" * 40
UPSTREAM = {
    "publication_package_directory": Path("publication-package"),
    "publication_attestation_path": Path("publication-attestation.json"),
    "publication_scenario": "full-confirmation",
    "phase01_artifact_directory": Path("phase01"),
    "phase02_artifact_directory": Path("phase02"),
    "phase03_artifact_directory": Path("phase03"),
    "expected_commit_sha": COMMIT,
}


def _probe(category: str, attack: str) -> dict:
    outcome = (
        AUTHORITY_LAUNDERING_OUTCOMES[attack]
        if category == "AUTHORITY_LAUNDERING"
        else f"{category}_BLOCKED"
    )
    content = {"category": category, "attack": attack, "expected": outcome}
    return {
        "probe_id": ("urn:kg-mnp:test-fixture:phase04:probe:" + semantic_hash(content)),
        "category": category,
        "attack": attack,
        "expected_outcome": outcome,
        "actual_outcome": outcome,
        "blocked": True,
        "status": "PASS",
    }


def _probes() -> list[dict]:
    result = [
        _probe(category, category.casefold())
        for category in CATEGORY_FIELDS
        if category != "AUTHORITY_LAUNDERING"
    ]
    result.extend(
        _probe("AUTHORITY_LAUNDERING", attack)
        for attack in sorted(AUTHORITY_LAUNDERING_ATTACKS)
    )
    return result


def _attestation(auth, workspace: dict, fixture, probes):
    probe_counts = {
        field: sum(probe["category"] == category for probe in probes)
        for category, fields in CATEGORY_FIELDS.items()
        for field in fields
    }
    laundering = sum(probe["category"] == "AUTHORITY_LAUNDERING" for probe in probes)
    return {
        "contract_version": "1.0",
        "commit_sha": COMMIT,
        "stage08_baseline": "4dc09d9cfb15da3746f108755593ceb9fe805cd7",
        "phase01_baseline": "79b7d34125b0c5cb2d5fe8546e1f4e6a95ca8106",
        "phase02_baseline": "3ef40b9cfbd657b55d8c5f446cfc247335db87f0",
        "phase03_baseline": "06898e8ef3fbe93bd7e7a030f4361c0bef7a76c9",
        "upstream_verification_mode": "EXACT_SHA_REMOTE_LICENSED_EVIDENCE",
        **auth.binding,
        "upstream_phase03_issues_total": auth.upstream_phase03_issues_total,
        # Tests patch this to the real contract hash after contract migration.
        "governance_contract_hash": verifier_module.governance_contract_hash(),
        "production_workspace_hash": workspace["workspace_hash"],
        "production_workspace_revision": workspace["workspace_revision"],
        "production_proposals_created": 0,
        "production_reviews_approved": 0,
        "production_reviews_rejected": 0,
        "production_reviews_deferred": 0,
        "production_amendment_requests": 0,
        "controlled_fixture_hash": fixture.controlled_fixture_hash,
        "controlled_fixture_diagnostic_package_hash": (
            fixture.controlled_fixture_diagnostic_package_hash
        ),
        "controlled_fixture_status": fixture.status,
        "controlled_scenarios_total": len(probes),
        "controlled_scenarios_passed": len(probes),
        "authority_laundering_attempts": laundering,
        "authority_laundering_blocked": laundering,
        **probe_counts,
        "repository_expected_hash": auth.repository_semantic_hash,
        "repository_before_hash": auth.repository_semantic_hash,
        "repository_after_hash": auth.repository_semantic_hash,
        "repository_unchanged": True,
        "upstream_phase03_hash_before": (auth.upstream_phase03_diagnostic_package_hash),
        "upstream_phase03_hash_after": (auth.upstream_phase03_diagnostic_package_hash),
        "upstream_phase03_unchanged": True,
        "status": "APPLICATION_HUMAN_GOVERNANCE_VERIFIED",
    }


def artifact(tmp_path: Path):
    # Production zero-issue authority is legal. The independent-loader unit tests
    # use this structural stub as the loader's result; construction security is
    # covered separately by the exact-upstream loader tests.
    controlled = authority()

    class VerifiedProductionAuthorityStub:
        authority_type = "PRODUCTION_EXACT_PHASE03"
        publication_id = controlled.publication_id
        publication_semantic_hash = controlled.publication_semantic_hash
        repository_semantic_hash = controlled.repository_semantic_hash
        upstream_phase03_attestation_sha256 = "1" * 64
        upstream_phase03_diagnostic_package_hash = "0" * 64
        upstream_phase03_issues_total = 0

        @property
        def binding(self):
            return {
                "authority_type": self.authority_type,
                "publication_id": self.publication_id,
                "publication_semantic_hash": self.publication_semantic_hash,
                "repository_semantic_hash": self.repository_semantic_hash,
                "upstream_phase03_attestation_sha256": (
                    self.upstream_phase03_attestation_sha256
                ),
                "upstream_phase03_diagnostic_package_hash": (
                    self.upstream_phase03_diagnostic_package_hash
                ),
            }

        def assert_same_current_authority(self, expected):
            if expected != self.binding:
                raise AssertionError("authority binding mismatch")

    auth = VerifiedProductionAuthorityStub()
    workspace = GovernanceWorkspace.initialize(auth).value
    fixture = ControlledDiagnosticFixture.create()
    probes = _probes()
    attestation = _attestation(auth, workspace, fixture, probes)
    controlled_summary = {
        "fixture_type": fixture.fixture_type,
        "test_only": True,
        "production_authority": False,
        "controlled_fixture_hash": fixture.controlled_fixture_hash,
        "controlled_fixture_diagnostic_package_hash": (
            fixture.controlled_fixture_diagnostic_package_hash
        ),
        "controlled_fixture_status": fixture.status,
        "diagnostic_issues": 4,
        "proposals_created": 5,
        "proposals_submitted": 5,
        "reviews_approved": 3,
        "reviews_rejected": 1,
        "reviews_deferred": 1,
        "amendment_requests": 3,
        "status": "PASS",
    }
    documents = {
        "application-phase04-attestation.json": attestation,
        "governance-summary.json": {
            "contract_version": "1.0",
            "production_workspace": workspace,
            "production_workspace_hash": workspace["workspace_hash"],
            "production_workspace_revision": workspace["workspace_revision"],
            "production_issues_total": 0,
            "production_proposals_created": 0,
            "production_reviews_approved": 0,
            "production_reviews_rejected": 0,
            "production_reviews_deferred": 0,
            "production_amendment_requests": 0,
            "controlled_scenario_summary": controlled_summary,
            "status": "PASS",
        },
        "state-machine-summary.json": {
            "contract_version": "1.0",
            "valid_transitions": [
                "DRAFT->SUBMITTED",
                "SUBMITTED->APPROVED_FOR_AMENDMENT",
                "SUBMITTED->REJECTED",
                "SUBMITTED->DEFERRED",
            ],
            "invalid_transition_probes": [
                probe["probe_id"]
                for probe in probes
                if probe["category"] == "ILLEGAL_TRANSITION"
            ],
            "status": "PASS",
        },
        "authority-binding.json": {
            "contract_version": "1.0",
            **auth.binding,
            "status": "PASS",
        },
        "security-summary.json": {
            "contract_version": "1.0",
            "probe_authority_mode": "CONTROLLED_TEST_FIXTURE",
            "production_authority": False,
            "test_only": True,
            "probes": probes,
            "external_requests": 0,
            "service_workers": 0,
            "status": "PASS",
        },
    }
    root = tmp_path / "artifact"
    root.mkdir(parents=True)
    for name, value in documents.items():
        (root / name).write_bytes(canonical_json_bytes(value) + b"\n")
    assert set(documents) == FILES
    return root, auth, documents


def _rewrite(root: Path, name: str, value: dict) -> None:
    (root / name).write_bytes(canonical_json_bytes(value) + b"\n")


def _verify(monkeypatch, root: Path, auth, **kwargs):
    seen = []

    def load(**arguments):
        seen.append(arguments)
        return auth

    monkeypatch.setattr(verifier_module, "load_production_phase03_authority", load)
    arguments = {**UPSTREAM, **kwargs}
    result = verify_application_phase04_artifact(root, **arguments)
    assert seen == [UPSTREAM]
    return result


def test_verifier_api_has_no_authority_injection() -> None:
    parameters = inspect.signature(verify_application_phase04_artifact).parameters
    assert "authority" not in parameters
    assert "authority_snapshot" not in parameters
    assert "diagnostic_package" not in parameters
    assert set(UPSTREAM) <= set(parameters)


def test_verifier_rejects_controlled_authority_from_loader(
    tmp_path: Path, monkeypatch
) -> None:
    root, _, _ = artifact(tmp_path)
    monkeypatch.setattr(
        verifier_module,
        "load_production_phase03_authority",
        lambda **_arguments: authority(),
    )
    with pytest.raises(
        Phase04ArtifactVerificationError,
        match="TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY",
    ):
        verify_application_phase04_artifact(root, **UPSTREAM)


def test_exact_artifact_reconstructs_zero_issue_production_authority(
    tmp_path: Path, monkeypatch
) -> None:
    root, auth, documents = artifact(tmp_path)
    result = _verify(
        monkeypatch,
        root,
        auth,
        expected_workspace_hash=documents["governance-summary.json"][
            "production_workspace_hash"
        ],
    )
    assert result["status"] == "APPLICATION_HUMAN_GOVERNANCE_VERIFIED"
    assert result["artifact_files"] == sorted(FILES)
    assert documents["governance-summary.json"]["production_issues_total"] == 0
    assert documents["governance-summary.json"]["production_proposals_created"] == 0


def test_closed_set_and_commit_binding_fail_closed(tmp_path: Path, monkeypatch) -> None:
    root, auth, _ = artifact(tmp_path)
    (root / "unexpected.json").write_text("{}", encoding="utf-8")
    with pytest.raises(Phase04ArtifactVerificationError, match="closed set"):
        _verify(monkeypatch, root, auth)
    (root / "unexpected.json").unlink()
    documents = copy.deepcopy(artifact(tmp_path / "second")[2])
    # The loader sees the trusted SHA; the independently read attestation does not.
    documents["application-phase04-attestation.json"]["commit_sha"] = "2" * 40
    attacked = tmp_path / "attacked"
    attacked.mkdir()
    for name, value in documents.items():
        _rewrite(attacked, name, value)
    with pytest.raises(Phase04ArtifactVerificationError, match="commit"):
        _verify(monkeypatch, attacked, auth)


def test_fixture_authority_full_rehash_substitution_rejected(
    tmp_path: Path, monkeypatch
) -> None:
    root, real, documents = artifact(tmp_path)
    fixture = ControlledDiagnosticFixture.create()
    replacement = copy.deepcopy(documents)
    fake_hash = fixture.controlled_fixture_diagnostic_package_hash
    fake_attestation = semantic_hash({"fake": True, "package": fake_hash})
    binding = replacement["authority-binding.json"]
    binding["authority_type"] = "PRODUCTION_EXACT_PHASE03"
    binding["upstream_phase03_attestation_sha256"] = fake_attestation
    binding["upstream_phase03_diagnostic_package_hash"] = fake_hash
    replacement["application-phase04-attestation.json"].update(
        {
            "upstream_phase03_attestation_sha256": fake_attestation,
            "upstream_phase03_diagnostic_package_hash": fake_hash,
            "upstream_phase03_hash_before": fake_hash,
            "upstream_phase03_hash_after": fake_hash,
        }
    )
    workspace = replacement["governance-summary.json"]["production_workspace"]
    workspace["authority_binding"] = {key: binding[key] for key in real.binding}
    workspace["workspace_id"] = "urn:kg-mnp:governance-workspace:" + semantic_hash(
        workspace["authority_binding"]
    )
    from kg_mnp_demo.governance.validator import workspace_semantic_content

    workspace["workspace_hash"] = semantic_hash(workspace_semantic_content(workspace))
    replacement["governance-summary.json"]["production_workspace_hash"] = workspace[
        "workspace_hash"
    ]
    replacement["application-phase04-attestation.json"]["production_workspace_hash"] = (
        workspace["workspace_hash"]
    )
    for name, value in replacement.items():
        _rewrite(root, name, value)
    with pytest.raises(
        Phase04ArtifactVerificationError,
        match="UPSTREAM_PHASE03_AUTHORITY_MISMATCH",
    ):
        _verify(monkeypatch, root, real)


def test_authority_laundering_matrix_is_exact(tmp_path: Path, monkeypatch) -> None:
    root, auth, documents = artifact(tmp_path)
    security = copy.deepcopy(documents["security-summary.json"])
    attack = next(
        probe
        for probe in security["probes"]
        if probe["category"] == "AUTHORITY_LAUNDERING"
    )
    attack["attack"] = "self_consistent_but_incomplete_matrix"
    attack["probe_id"] = (
        "urn:kg-mnp:test-fixture:phase04:probe:"
        + semantic_hash(
            {
                "category": attack["category"],
                "attack": attack["attack"],
                "expected": attack["expected_outcome"],
            }
        )
    )
    _rewrite(root, "security-summary.json", security)
    with pytest.raises(Phase04ArtifactVerificationError, match="attack matrix"):
        _verify(monkeypatch, root, auth)


def test_laundering_outcomes_cannot_be_self_reported_as_accepted(
    tmp_path: Path, monkeypatch
) -> None:
    root, auth, documents = artifact(tmp_path)
    security = copy.deepcopy(documents["security-summary.json"])
    for probe in security["probes"]:
        if probe["category"] != "AUTHORITY_LAUNDERING":
            continue
        probe["expected_outcome"] = "ACCEPTED"
        probe["actual_outcome"] = "ACCEPTED"
        probe["probe_id"] = (
            "urn:kg-mnp:test-fixture:phase04:probe:"
            + semantic_hash(
                {
                    "category": probe["category"],
                    "attack": probe["attack"],
                    "expected": "ACCEPTED",
                }
            )
        )
    _rewrite(root, "security-summary.json", security)
    with pytest.raises(Phase04ArtifactVerificationError, match="attack matrix"):
        _verify(monkeypatch, root, auth)


@pytest.mark.parametrize(
    "value", ["C:/Users/alice/private", "GRAPHDB_LICENSE_CONTENT=secret"]
)
def test_absolute_paths_and_secrets_are_rejected(
    tmp_path: Path, monkeypatch, value: str
) -> None:
    root, auth, documents = artifact(tmp_path)
    security = copy.deepcopy(documents["security-summary.json"])
    security["probes"][0]["expected_outcome"] = value
    security["probes"][0]["actual_outcome"] = value
    _rewrite(root, "security-summary.json", security)
    with pytest.raises(Phase04ArtifactVerificationError, match="secret or absolute"):
        _verify(monkeypatch, root, auth)
