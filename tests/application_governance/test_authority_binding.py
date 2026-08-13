from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from application._phase01_helpers import publication_attestation_report
from workbench.test_workbench_artifact import (
    write_artifact as write_phase02_artifact,
)

import kg_mnp_demo.governance.authority_binding as authority_binding_module
from kg_mnp_demo.diagnostics.attestation import (
    build_application_phase03_attestation,
)
from kg_mnp_demo.diagnostics.authority_loader import (
    load_verified_authority_bindings,
)
from kg_mnp_demo.diagnostics.contracts import strict_json_file
from kg_mnp_demo.diagnostics.engine import AuthoritySnapshot, reconstruct_diagnostics
from kg_mnp_demo.governance.authority_binding import (
    PRODUCTION_AUTHORITY_TYPE,
    GovernanceAuthority,
    load_production_phase03_authority,
)
from kg_mnp_demo.governance.errors import GovernanceError, GovernanceErrorCode
from kg_mnp_demo.governance.workspace import GovernanceWorkspace
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "1" * 40


def _write_phase03_artifact(
    directory: Path,
    *,
    authority_bindings,
    package: Mapping[str, Any],
    commit_sha: str = COMMIT,
) -> Path:
    attestation = build_application_phase03_attestation(
        commit_sha=commit_sha,
        authority_bindings=authority_bindings,
        package=package,
        repository_before_hash=authority_bindings.repository_semantic_hash,
        repository_after_hash=authority_bindings.repository_semantic_hash,
        controlled_scenarios_total=4,
        controlled_scenarios_passed=4,
        determinism_runs=2,
        determinism_passed=True,
        permutation_attacks=1,
        permutation_passed=True,
        authority_tamper_attempts=1,
        authority_tamper_blocked=1,
        missingness_attacks=1,
        missingness_expected_results=1,
        conflict_attacks=1,
        conflict_expected_results=1,
        evidence_attacks=1,
        evidence_expected_results=1,
        xss_attempts=1,
        xss_blocked=1,
        external_requests=0,
        direct_graphdb_attempts=1,
        direct_graphdb_blocked=1,
    )
    documents = {
        "application-phase03-attestation.json": attestation,
        "diagnostics-summary.json": {
            "contract_version": "1.0",
            "diagnostic_package_hash": attestation["diagnostic_package_hash"],
            "issues_total": attestation["issues_total"],
            "issues_by_classification": attestation["issues_by_classification"],
            "requirements_evaluated": attestation["requirements_evaluated"],
            "constraints_evaluated": attestation["constraints_evaluated"],
            "status": "PASS",
        },
        "diagnostic-determinism.json": {
            "contract_version": "1.0",
            "diagnostic_package_hash": attestation["diagnostic_package_hash"],
            "determinism_runs": 2,
            "canonical_hashes": [attestation["diagnostic_package_hash"]] * 2,
            "determinism_passed": True,
            "permutation_attacks": 1,
            "permutation_passed": True,
            "status": "PASS",
        },
        "authority-binding.json": {
            "contract_version": "1.0",
            **authority_bindings.to_dict(),
            "status": "PASS",
        },
        "security-summary.json": {
            "contract_version": "1.0",
            **{
                key: attestation[key]
                for key in (
                    "authority_tamper_attempts",
                    "authority_tamper_blocked",
                    "missingness_attacks",
                    "missingness_expected_results",
                    "conflict_attacks",
                    "conflict_expected_results",
                    "evidence_attacks",
                    "evidence_expected_results",
                    "xss_attempts",
                    "xss_blocked",
                    "external_requests",
                    "direct_graphdb_attempts",
                    "direct_graphdb_blocked",
                )
            },
            "status": "PASS",
        },
    }
    directory.mkdir()
    for name, value in documents.items():
        (directory / name).write_bytes(canonical_json_bytes(value) + b"\n")
    return directory


@pytest.fixture(scope="module")
def exact_upstream(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase04-exact-authority")
    publication_package = ROOT / "examples/publication/expected/full-confirmation"
    publication_attestation = publication_attestation_report(
        root / "publication-attestation", "full-confirmation"
    )
    phase02 = root / "phase02"
    write_phase02_artifact(phase02, root)
    phase01 = root / "phase01"
    bindings = load_verified_authority_bindings(
        publication_manifest=strict_json_file(
            publication_package / "publication-manifest.json"
        ),
        phase01_artifact_directory=phase01,
        phase02_artifact_directory=phase02,
    )
    # The production loader itself calls the full Stage08/Phase01/Phase02
    # authority reconstruction.  These focused unit tests replace only that slow
    # verified boundary with an equivalent immutable snapshot; licensed
    # integration exercises the complete reconstruction path.
    snapshot = AuthoritySnapshot(
        authority_bindings=bindings,
        requirements=(),
        facts=(),
    )
    package = reconstruct_diagnostics(snapshot).to_dict()
    phase03 = _write_phase03_artifact(
        root / "phase03",
        authority_bindings=snapshot.authority_bindings,
        package=package,
    )
    return {
        "root": root,
        "publication_package": publication_package,
        "publication_attestation": publication_attestation,
        "phase01": phase01,
        "phase02": phase02,
        "phase03": phase03,
        "snapshot": snapshot,
        "package": package,
    }


def _load(
    paths,
    monkeypatch,
    *,
    phase03: Path | None = None,
    commit_sha: str = COMMIT,
):
    seen = []

    def verified_snapshot(**arguments):
        seen.append(arguments)
        return paths["snapshot"]

    monkeypatch.setattr(
        authority_binding_module,
        "load_verified_authority_snapshot",
        verified_snapshot,
    )
    return load_production_phase03_authority(
        publication_package_directory=paths["publication_package"],
        publication_attestation_path=paths["publication_attestation"],
        publication_scenario="full-confirmation",
        phase01_artifact_directory=paths["phase01"],
        phase02_artifact_directory=paths["phase02"],
        phase03_artifact_directory=phase03 or paths["phase03"],
        expected_commit_sha=commit_sha,
    )


def test_exact_phase03_is_reconstructed_and_physically_bound(
    exact_upstream, monkeypatch
) -> None:
    authority = _load(exact_upstream, monkeypatch)
    attestation_path = (
        exact_upstream["phase03"] / "application-phase03-attestation.json"
    )
    assert authority.authority_type == PRODUCTION_AUTHORITY_TYPE
    assert authority.upstream_phase03_attestation_sha256 == hashlib.sha256(
        attestation_path.read_bytes()
    ).hexdigest()
    assert authority.upstream_phase03_diagnostic_package_hash == (
        exact_upstream["package"]["manifest"]["package_semantic_hash"]
    )
    assert set(authority.binding) == {
        "authority_type",
        "publication_id",
        "publication_semantic_hash",
        "repository_semantic_hash",
        "upstream_phase03_attestation_sha256",
        "upstream_phase03_diagnostic_package_hash",
    }


def test_real_zero_issue_phase03_authority_is_valid(
    exact_upstream, monkeypatch
) -> None:
    authority = _load(exact_upstream, monkeypatch)
    assert exact_upstream["package"]["summary"]["issues_total"] == 0
    assert authority.upstream_phase03_issues_total == 0
    assert authority.issues == {}
    workspace = GovernanceWorkspace.initialize(authority)
    assert workspace.value["events"] == []
    assert workspace.value["workspace_revision"] == 0


def test_phase02_and_phase03_must_match_expected_exact_sha(
    exact_upstream, monkeypatch
) -> None:
    with pytest.raises(GovernanceError) as caught:
        _load(exact_upstream, monkeypatch, commit_sha="2" * 40)
    assert caught.value.code == GovernanceErrorCode.AUTHORITY_MISMATCH


def test_self_consistent_synthetic_phase03_authority_rejected(
    exact_upstream, monkeypatch
) -> None:
    bindings = exact_upstream["snapshot"].authority_bindings
    namespace = "urn:kg-mnp:test-fixture:phase04:laundering:"
    path = namespace + "property"
    synthetic_snapshot = {
        "authority_bindings": bindings.to_dict(),
        "requirements": [
            {
                "focus_node": namespace + "synthetic-requirement-focus",
                "path": path,
                "requirement_type": "CONTROLLED_SHACL_MIN_COUNT",
                "authority_iri": namespace + "constraint",
                "shape_iri": namespace + "shape",
                "constraint_iri": namespace + "constraint",
                "module": "self-consistent-authority-laundering-attack",
                "publication_id": bindings.publication_id,
                "min_count": 1,
                "max_count": 1,
            }
        ],
        "facts": [
            {
                "subject": namespace + "synthetic-fact-focus",
                "predicate": path,
                "object": "attacker-authored-value",
                "assertion_ref": namespace + "synthetic-assertion",
            }
        ],
        "constraint_results": [],
        "candidates": [
            {
                "focus_node": namespace + "synthetic-candidate-focus",
                "path": path,
                "value": "attacker-authored-candidate",
                "outcome": "REJECT",
                "candidate_ref": namespace + "synthetic-candidate",
                "review_decision_ref": namespace + "synthetic-decision",
                "evidence_refs": [],
                "source_refs": [],
            }
        ],
        "conflict_rules": [],
    }
    synthetic_package = reconstruct_diagnostics(synthetic_snapshot).to_dict()
    assert synthetic_package["authority_bindings"] == bindings.to_dict()
    assert synthetic_package["manifest"]["package_semantic_hash"] != (
        exact_upstream["package"]["manifest"]["package_semantic_hash"]
    )
    synthetic_phase03 = _write_phase03_artifact(
        exact_upstream["root"] / "synthetic-phase03",
        authority_bindings=bindings,
        package=synthetic_package,
    )

    # The replacement has copied publication/repository/commit identity and all
    # of its own Phase03 files and hashes are freshly self-consistent.  It still
    # cannot replace diagnostics reconstructed from the exact upstream lineage.
    with pytest.raises(GovernanceError) as caught:
        _load(exact_upstream, monkeypatch, phase03=synthetic_phase03)
    assert caught.value.code == GovernanceErrorCode.AUTHORITY_MISMATCH


def test_direct_construction_cannot_mint_production_authority(exact_upstream) -> None:
    package = exact_upstream["package"]
    bindings = package["authority_bindings"]
    with pytest.raises(GovernanceError) as caught:
        GovernanceAuthority(
            authority_type=PRODUCTION_AUTHORITY_TYPE,
            publication_id=bindings["publication_id"],
            publication_semantic_hash=bindings["publication_semantic_hash"],
            repository_semantic_hash=bindings["repository_semantic_hash"],
            upstream_phase03_attestation_sha256="a" * 64,
            upstream_phase03_diagnostic_package_hash=(
                package["manifest"]["package_semantic_hash"]
            ),
            issues={},
        )
    assert caught.value.code == GovernanceErrorCode.AUTHORITY_MISMATCH


def test_governance_authority_exposes_no_production_factory() -> None:
    assert not hasattr(GovernanceAuthority, "_from_verified_production")
    assert not hasattr(authority_binding_module, "_PRODUCTION_CONSTRUCTION_CAPABILITY")
    assert load_production_phase03_authority.__closure__ is None


def test_internal_assignment_cannot_mint_production_authority(
    exact_upstream,
) -> None:
    value = object.__new__(GovernanceAuthority)
    assert not hasattr(value, "_assign")


def test_imported_internal_helpers_cannot_register_forged_production_authority(
    exact_upstream,
) -> None:
    bindings = exact_upstream["snapshot"].authority_bindings
    value = object.__new__(GovernanceAuthority)
    for name, content in {
        "authority_type": PRODUCTION_AUTHORITY_TYPE,
        "publication_id": bindings.publication_id,
        "publication_semantic_hash": bindings.publication_semantic_hash,
        "repository_semantic_hash": bindings.repository_semantic_hash,
        "upstream_phase03_attestation_sha256": "a" * 64,
        "upstream_phase03_diagnostic_package_hash": "b" * 64,
        "_issue_documents": {},
    }.items():
        object.__setattr__(value, name, content)
    with pytest.raises(GovernanceError) as caught:
        GovernanceWorkspace.initialize(value)
    assert caught.value.code == GovernanceErrorCode.AUTHORITY_MISMATCH


def test_copied_exact_source_cannot_authorize_synthetic_diagnostics(
    exact_upstream, monkeypatch
) -> None:
    real = _load(exact_upstream, monkeypatch)
    forged = object.__new__(GovernanceAuthority)
    for name, content in {
        "authority_type": PRODUCTION_AUTHORITY_TYPE,
        "publication_id": real.publication_id,
        "publication_semantic_hash": real.publication_semantic_hash,
        "repository_semantic_hash": real.repository_semantic_hash,
        "upstream_phase03_attestation_sha256": (
            real.upstream_phase03_attestation_sha256
        ),
        "upstream_phase03_diagnostic_package_hash": "b" * 64,
        "_issue_documents": {
            "urn:kg-mnp:test-fixture:phase04:synthetic-issue": (
                canonical_json_bytes(
                    {
                        "diagnostic_id": (
                            "urn:kg-mnp:test-fixture:phase04:synthetic-issue"
                        ),
                        "classification": "REQUIRED_VALUE_MISSING",
                    }
                )
            )
        },
        # The attacker may inspect and copy this descriptor.  It is not a
        # credential: the production gate repeats the exact reconstruction.
        "_production_source": real._production_source,
    }.items():
        object.__setattr__(forged, name, content)

    with pytest.raises(GovernanceError) as caught:
        GovernanceWorkspace.initialize(forged)
    assert caught.value.code == GovernanceErrorCode.AUTHORITY_MISMATCH


def test_verified_gate_never_returns_caller_owned_mapping_semantics(
    exact_upstream, monkeypatch
) -> None:
    real = _load(exact_upstream, monkeypatch)
    synthetic_id = "urn:kg-mnp:test-fixture:phase04:synthetic-issue"
    synthetic_issue = {
        "diagnostic_id": synthetic_id,
        "diagnostic_basis_hash": "c" * 64,
        "classification": "REQUIRED_VALUE_MISSING",
    }

    class SplitViewIssues(Mapping):
        def __getitem__(self, key):
            if key == synthetic_id:
                return canonical_json_bytes(synthetic_issue)
            raise KeyError(key)

        def __iter__(self):
            return iter(())

        def __len__(self):
            return 0

        def items(self):
            return ().__iter__()

        def get(self, key, default=None):
            return self[key] if key == synthetic_id else default

    forged = object.__new__(GovernanceAuthority)
    for name, content in {
        "authority_type": PRODUCTION_AUTHORITY_TYPE,
        **real.binding,
        "_issue_documents": SplitViewIssues(),
        "_production_source": real._production_source,
    }.items():
        object.__setattr__(forged, name, content)

    verified = authority_binding_module._require_verified_production_authority(forged)
    assert verified is not forged
    assert verified.issues == {}
    with pytest.raises(GovernanceError) as caught:
        verified.require_issue(synthetic_id)
    assert caught.value.code == GovernanceErrorCode.UNKNOWN_DIAGNOSTIC


def test_authority_issue_projection_cannot_mutate_loaded_authority(
    exact_upstream,
) -> None:
    package = reconstruct_diagnostics(
        {
            "authority_bindings": exact_upstream[
                "snapshot"
            ].authority_bindings.to_dict(),
            "requirements": [
                {
                    "focus_node": "urn:kg-mnp:test-fixture:phase04:immutable:focus",
                    "path": "urn:kg-mnp:test-fixture:phase04:immutable:path",
                    "requirement_type": "CONTROLLED_SHACL_MIN_COUNT",
                    "authority_iri": (
                        "urn:kg-mnp:test-fixture:phase04:immutable:constraint"
                    ),
                    "module": "immutability-regression",
                    "publication_id": exact_upstream[
                        "snapshot"
                    ].authority_bindings.publication_id,
                    "min_count": 1,
                    "max_count": 1,
                }
            ],
            "facts": [],
        }
    ).to_dict()
    issue = package["issues"][0]
    authority = GovernanceAuthority(
        authority_type="CONTROLLED_TEST_HARNESS",
        publication_id=exact_upstream["snapshot"].authority_bindings.publication_id,
        publication_semantic_hash=exact_upstream[
            "snapshot"
        ].authority_bindings.publication_semantic_hash,
        repository_semantic_hash=exact_upstream[
            "snapshot"
        ].authority_bindings.repository_semantic_hash,
        upstream_phase03_attestation_sha256="a" * 64,
        upstream_phase03_diagnostic_package_hash=(
            package["manifest"]["package_semantic_hash"]
        ),
        issues={issue["diagnostic_id"]: issue},
    )

    projected = authority.issues[issue["diagnostic_id"]]
    projected["classification"] = "VALUE_UNKNOWN"
    projected["authority_basis"][0]["module"] = "attacker-mutated"

    reloaded = authority.require_issue(issue["diagnostic_id"])
    assert reloaded["classification"] == "REQUIRED_VALUE_MISSING"
    assert reloaded["authority_basis"][0]["module"] == "immutability-regression"


def test_upstream_artifact_tree_change_during_reconstruction_is_rejected(
    exact_upstream, monkeypatch
) -> None:
    marker = exact_upstream["phase01"] / "security-summary.json"
    original = marker.read_bytes()

    def mutate_upstream(**_arguments):
        marker.write_bytes(original + b" ")
        return exact_upstream["snapshot"]

    monkeypatch.setattr(
        authority_binding_module,
        "load_verified_authority_snapshot",
        mutate_upstream,
    )
    try:
        with pytest.raises(GovernanceError) as caught:
            load_production_phase03_authority(
                publication_package_directory=exact_upstream[
                    "publication_package"
                ],
                publication_attestation_path=exact_upstream[
                    "publication_attestation"
                ],
                phase01_artifact_directory=exact_upstream["phase01"],
                phase02_artifact_directory=exact_upstream["phase02"],
                phase03_artifact_directory=exact_upstream["phase03"],
                expected_commit_sha=COMMIT,
            )
        assert caught.value.code == GovernanceErrorCode.AUTHORITY_MISMATCH
    finally:
        marker.write_bytes(original)


def test_phase03_artifact_tree_change_during_verification_is_rejected(
    exact_upstream, monkeypatch
) -> None:
    marker = exact_upstream["phase03"] / "security-summary.json"
    original = marker.read_bytes()
    real_verify = authority_binding_module.verify_application_phase03_artifact

    def mutate_phase03(*arguments, **keywords):
        verified = real_verify(*arguments, **keywords)
        marker.write_bytes(original + b" ")
        return verified

    monkeypatch.setattr(
        authority_binding_module,
        "verify_application_phase03_artifact",
        mutate_phase03,
    )
    try:
        with pytest.raises(GovernanceError) as caught:
            _load(exact_upstream, monkeypatch)
        assert caught.value.code == GovernanceErrorCode.AUTHORITY_MISMATCH
    finally:
        marker.write_bytes(original)


def test_loaded_authority_is_reverified_before_production_workspace_use(
    exact_upstream, monkeypatch
) -> None:
    authority = _load(exact_upstream, monkeypatch)
    marker = (
        exact_upstream["phase03"] / "application-phase03-attestation.json"
    )
    original = marker.read_bytes()
    marker.write_bytes(original + b" ")
    try:
        with pytest.raises(GovernanceError) as caught:
            GovernanceWorkspace.initialize(authority)
        assert caught.value.code == GovernanceErrorCode.AUTHORITY_MISMATCH
    finally:
        marker.write_bytes(original)
