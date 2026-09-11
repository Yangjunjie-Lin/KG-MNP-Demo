"""Application Phase 03 closure attestation construction."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .authority_binding import AuthorityBindings
from .contracts import validate_diagnostic_contract
from .package import DeterministicDiagnosticPackage
from .validator import validate_diagnostic_package

STAGE08_BASELINE_SHA = "4dc09d9cfb15da3746f108755593ceb9fe805cd7"
PHASE01_BASELINE_SHA = "79b7d34125b0c5cb2d5fe8546e1f4e6a95ca8106"
PHASE02_BASELINE_SHA = "3ef40b9cfbd657b55d8c5f446cfc247335db87f0"


def build_application_phase03_attestation(
    *,
    commit_sha: str,
    authority_bindings: AuthorityBindings,
    package: DeterministicDiagnosticPackage | Mapping[str, Any],
    repository_before_hash: str,
    repository_after_hash: str,
    controlled_scenarios_total: int,
    controlled_scenarios_passed: int,
    determinism_runs: int,
    determinism_passed: bool,
    permutation_attacks: int,
    permutation_passed: bool,
    authority_tamper_attempts: int,
    authority_tamper_blocked: int,
    missingness_attacks: int,
    missingness_expected_results: int,
    conflict_attacks: int,
    conflict_expected_results: int,
    evidence_attacks: int,
    evidence_expected_results: int,
    xss_attempts: int,
    xss_blocked: int,
    external_requests: int,
    direct_graphdb_attempts: int,
    direct_graphdb_blocked: int,
) -> dict[str, Any]:
    value = validate_diagnostic_package(
        package.to_dict()
        if isinstance(package, DeterministicDiagnosticPackage)
        else package
    )
    coverage = value["coverage"]
    repository_unchanged = (
        authority_bindings.repository_semantic_hash
        == repository_before_hash
        == repository_after_hash
    )
    verified = (
        repository_unchanged
        and controlled_scenarios_total == controlled_scenarios_passed == 4
        and determinism_runs >= 2
        and determinism_passed is True
        and permutation_attacks > 0
        and permutation_passed is True
        and authority_tamper_attempts > 0
        and authority_tamper_attempts == authority_tamper_blocked
        and missingness_attacks > 0
        and missingness_attacks == missingness_expected_results
        and conflict_attacks > 0
        and conflict_attacks == conflict_expected_results
        and evidence_attacks > 0
        and evidence_attacks == evidence_expected_results
        and xss_attempts > 0
        and xss_attempts == xss_blocked
        and external_requests == 0
        and direct_graphdb_attempts > 0
        and direct_graphdb_attempts == direct_graphdb_blocked
    )
    payload = {
        "contract_version": "1.0",
        "commit_sha": commit_sha,
        "stage08_baseline": STAGE08_BASELINE_SHA,
        "phase01_baseline": PHASE01_BASELINE_SHA,
        "phase02_baseline": PHASE02_BASELINE_SHA,
        "publication_id": authority_bindings.publication_id,
        "publication_semantic_hash": authority_bindings.publication_semantic_hash,
        "phase01_attestation_hash": authority_bindings.phase01_attestation_hash,
        "phase02_attestation_hash": authority_bindings.phase02_attestation_hash,
        "query_registry_hash": authority_bindings.query_registry_hash,
        "repository_expected_hash": authority_bindings.repository_semantic_hash,
        "repository_before_hash": repository_before_hash,
        "repository_after_hash": repository_after_hash,
        "repository_unchanged": repository_unchanged,
        "diagnostic_policy_hash": authority_bindings.diagnostic_policy_hash,
        "diagnostic_package_hash": value["manifest"]["package_semantic_hash"],
        "issues_total": value["summary"]["issues_total"],
        "issues_by_classification": value["summary"]["issues_by_classification"],
        "requirements_evaluated": coverage["requirements_evaluated"],
        "constraints_evaluated": coverage["shacl_constraints_evaluated"],
        "controlled_scenarios_total": controlled_scenarios_total,
        "controlled_scenarios_passed": controlled_scenarios_passed,
        "determinism_runs": determinism_runs,
        "determinism_passed": determinism_passed,
        "permutation_attacks": permutation_attacks,
        "permutation_passed": permutation_passed,
        "authority_tamper_attempts": authority_tamper_attempts,
        "authority_tamper_blocked": authority_tamper_blocked,
        "missingness_attacks": missingness_attacks,
        "missingness_expected_results": missingness_expected_results,
        "conflict_attacks": conflict_attacks,
        "conflict_expected_results": conflict_expected_results,
        "evidence_attacks": evidence_attacks,
        "evidence_expected_results": evidence_expected_results,
        "xss_attempts": xss_attempts,
        "xss_blocked": xss_blocked,
        "external_requests": external_requests,
        "direct_graphdb_attempts": direct_graphdb_attempts,
        "direct_graphdb_blocked": direct_graphdb_blocked,
        "status": "APPLICATION_DIAGNOSTICS_VERIFIED" if verified else "FAILED",
    }
    validate_diagnostic_contract("diagnostic-attestation", payload)
    return payload


build_diagnostics_attestation = build_application_phase03_attestation
