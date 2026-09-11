"""Independent verifier for the exact five-file Phase 05 artifact."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .authority_binding import (
    load_production_phase05_authority,
)
from .contracts import strict_json_bytes, validate_amendment_contract
from .errors import AmendmentError, AmendmentErrorCode

FILES = frozenset(
    {
        "application-phase05-attestation.json",
        "amendment-intake-summary.json",
        "republication-summary.json",
        "authority-binding.json",
        "security-summary.json",
    }
)
HASH = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


class Phase05ArtifactVerificationError(ValueError):
    """The exact Phase 05 artifact cannot be independently verified."""


def _exact(value: dict[str, Any], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise Phase05ArtifactVerificationError(f"{label} field set mismatch")


def _documents(directory: Path) -> dict[str, dict[str, Any]]:
    supplied = Path(directory)
    if supplied.is_symlink():
        raise Phase05ArtifactVerificationError("artifact directory is a symlink")
    root = supplied.resolve(strict=True)
    if not root.is_dir():
        raise Phase05ArtifactVerificationError("artifact is not a directory")
    entries = list(root.iterdir())
    if {path.name for path in entries} != FILES or any(
        path.is_symlink() or not path.is_file() for path in entries
    ):
        raise Phase05ArtifactVerificationError(
            "artifact exact five-file closed set mismatch"
        )
    frozen = {path.name: path.read_bytes() for path in entries}
    documents: dict[str, dict[str, Any]] = {}
    for name, raw in frozen.items():
        if len(raw) > 2 * 1024 * 1024:
            raise Phase05ArtifactVerificationError("artifact file is too large")
        try:
            value = strict_json_bytes(raw)
        except Exception as exc:
            raise Phase05ArtifactVerificationError(
                "invalid strict JSON artifact"
            ) from exc
        if not isinstance(value, dict):
            raise Phase05ArtifactVerificationError(
                "artifact JSON root is not an object"
            )
        documents[name] = value
    if any(path.read_bytes() != frozen[path.name] for path in entries):
        raise Phase05ArtifactVerificationError("artifact changed during verification")
    return documents


def verify_application_phase05_artifact(
    directory: Path,
    *,
    stage08_artifact: Path | None = None,
    phase01_artifact: Path | None = None,
    phase02_artifact: Path | None = None,
    phase03_artifact: Path | None = None,
    phase04_artifact: Path | None = None,
    publication_attestation: Path | None = None,
    expected_commit_sha: str | None = None,
    publication_scenario: str = "full-confirmation",
) -> dict[str, Any]:
    """Verify an artifact and reconstruct, rather than accept, production authority."""

    if not all(
        value is not None
        for value in (
            stage08_artifact,
            phase01_artifact,
            phase02_artifact,
            phase03_artifact,
            phase04_artifact,
            expected_commit_sha,
        )
    ):
        raise Phase05ArtifactVerificationError(
            "exact Stage08--Phase04 artifact paths and expected commit SHA are required"
        )
    if not COMMIT.fullmatch(str(expected_commit_sha)):
        raise Phase05ArtifactVerificationError("invalid expected commit SHA")
    try:
        authority = load_production_phase05_authority(
            stage08_artifact=Path(stage08_artifact),
            phase01_artifact=Path(phase01_artifact),
            phase02_artifact=Path(phase02_artifact),
            phase03_artifact=Path(phase03_artifact),
            phase04_artifact=Path(phase04_artifact),
            expected_commit_sha=str(expected_commit_sha),
            publication_scenario=publication_scenario,
            publication_attestation=publication_attestation,
        )
    except Exception as exc:
        raise Phase05ArtifactVerificationError(
            "production authority reconstruction failed"
        ) from exc
    documents = _documents(directory)
    attestation = documents["application-phase05-attestation.json"]
    try:
        validate_amendment_contract("application-phase05-attestation", attestation)
    except Exception as exc:
        raise Phase05ArtifactVerificationError("attestation schema failed") from exc
    if (
        attestation["commit_sha"] != expected_commit_sha
        or attestation["status"] != "APPLICATION_AMENDMENT_REPUBLICATION_VERIFIED"
        or attestation["upstream_phase04_attestation_sha256"]
        != authority.phase04_attestation_sha256
        or attestation["upstream_phase04_workspace_hash"]
        != authority.phase04_workspace_hash
        or attestation["production_pending_amendments"]
        != authority.production_pending_amendments
        or authority.production_pending_amendments != 0
        or attestation["production_reentry_cycles"] != 0
        or attestation["production_new_publications"] != 0
        or attestation["determinism_runs"] < 2
        or attestation["determinism_runs"] != attestation["determinism_passed"]
    ):
        raise Phase05ArtifactVerificationError("upstream production authority mismatch")

    binding = documents["authority-binding.json"]
    _exact(
        binding, {"contract_version", *authority.binding, "status"}, "authority binding"
    )
    if binding != {"contract_version": "1.0", **authority.binding, "status": "PASS"}:
        raise Phase05ArtifactVerificationError("authority binding mismatch")

    intake = documents["amendment-intake-summary.json"]
    _exact(
        intake,
        {
            "contract_version",
            "fixture_type",
            "test_only",
            "production_authority",
            "controlled_fixture_hash",
            "controlled_amendment_type",
            "intake_id",
            "intake_manifest_hash",
            "approved_amendment_request_id",
            "base_cleaned_data_hash",
            "revised_cleaned_data_hash",
            "declared_json_diff",
            "actual_json_diff",
            "status",
        },
        "amendment intake summary",
    )
    try:
        from scripts.amendment_controlled_fixture import (
            run_controlled_republication_harness,
        )
    except ModuleNotFoundError:
        from amendment_controlled_fixture import (  # type: ignore[import-not-found]
            run_controlled_republication_harness,
        )

    controlled_reconstruction = run_controlled_republication_harness()
    if not (
        intake["fixture_type"] == "PHASE05_CONTROLLED_AMENDMENT_FIXTURE"
        and intake["test_only"] is True
        and intake["production_authority"] is False
        and HASH.fullmatch(intake["controlled_fixture_hash"])
        and intake["declared_json_diff"] == intake["actual_json_diff"]
        and intake["status"] == "PASS"
        and intake["controlled_fixture_hash"] == attestation["controlled_fixture_hash"]
        and intake["controlled_fixture_hash"]
        == controlled_reconstruction["controlled_fixture_hash"]
        and intake["controlled_amendment_type"]
        == controlled_reconstruction["controlled_amendment_type"]
        and intake["intake_id"] == controlled_reconstruction["intake_id"]
        and intake["intake_manifest_hash"]
        == controlled_reconstruction["intake_manifest_hash"]
        and intake["approved_amendment_request_id"]
        == controlled_reconstruction["approved_amendment_request_id"]
        and intake["base_cleaned_data_hash"]
        == controlled_reconstruction["base_cleaned_data_hash"]
        and intake["revised_cleaned_data_hash"]
        == controlled_reconstruction["revised_cleaned_data_hash"]
        and intake["declared_json_diff"]
        == controlled_reconstruction["declared_json_diff"]
        and intake["actual_json_diff"] == controlled_reconstruction["actual_json_diff"]
    ):
        raise Phase05ArtifactVerificationError("controlled fixture separation mismatch")

    republication = documents["republication-summary.json"]
    _exact(
        republication,
        {
            "contract_version",
            "test_only",
            "production_authority",
            "controlled_reentry_cycles",
            "controlled_republication_cycles",
            "review_reject_no_publication",
            "review_defer_no_publication",
            "old_publication_immutable",
            "old_repository_immutable",
            "old_publication_package_before_sha256",
            "old_publication_package_after_sha256",
            "old_graphdb_package_before_sha256",
            "old_graphdb_package_after_sha256",
            "old_repository_id",
            "new_repository_id",
            "old_modeling_proposal_hash",
            "new_modeling_proposal_hash",
            "new_review_decision_log_hash",
            "new_confirmed_modeling_package_hash",
            "old_phase03_diagnostic_package_hash",
            "new_phase03_diagnostic_package_hash",
            "amendment_lineage",
            "governance_provenance_separate_from_business_evidence",
            "old_tbox_hash",
            "new_tbox_hash",
            "old_shacl_hash",
            "new_shacl_hash",
            "old_abox_hash",
            "new_abox_hash",
            "old_publication_hash",
            "new_publication_hash",
            "old_webvowl_hash",
            "new_webvowl_hash",
            "target_diagnostic_before",
            "target_diagnostic_after",
            "status",
        },
        "republication summary",
    )
    if not (
        republication["test_only"] is True
        and republication["production_authority"] is False
        and republication["status"] == "PASS"
        and republication["controlled_reentry_cycles"]
        == attestation["controlled_reentry_cycles"]
        and republication["controlled_republication_cycles"]
        == attestation["controlled_republication_cycles"]
        and republication["controlled_reentry_cycles"] > 0
        and republication["controlled_republication_cycles"] > 0
        and republication["review_reject_no_publication"] is True
        and republication["review_defer_no_publication"] is True
        and republication["review_reject_no_publication"]
        == controlled_reconstruction["review_reject_no_publication"]
        and republication["review_defer_no_publication"]
        == controlled_reconstruction["review_defer_no_publication"]
        and republication["old_publication_immutable"] is True
        and republication["old_repository_immutable"] is True
        and republication["old_publication_package_before_sha256"]
        == republication["old_publication_package_after_sha256"]
        and republication["old_graphdb_package_before_sha256"]
        == republication["old_graphdb_package_after_sha256"]
        and republication["old_repository_id"] != republication["new_repository_id"]
        and all(
            republication[field] == controlled_reconstruction[field]
            for field in (
                "old_publication_package_before_sha256",
                "old_publication_package_after_sha256",
                "old_graphdb_package_before_sha256",
                "old_graphdb_package_after_sha256",
                "old_repository_id",
                "new_repository_id",
            )
        )
        and republication["governance_provenance_separate_from_business_evidence"]
        is True
        and all(
            republication[field] == controlled_reconstruction[field]
            for field in (
                "old_modeling_proposal_hash",
                "new_modeling_proposal_hash",
                "new_review_decision_log_hash",
                "new_confirmed_modeling_package_hash",
                "old_phase03_diagnostic_package_hash",
                "new_phase03_diagnostic_package_hash",
                "amendment_lineage",
                "governance_provenance_separate_from_business_evidence",
            )
        )
        and republication["old_tbox_hash"] == republication["new_tbox_hash"]
        and republication["old_shacl_hash"] == republication["new_shacl_hash"]
        and republication["old_webvowl_hash"] == republication["new_webvowl_hash"]
        and republication["old_abox_hash"] != republication["new_abox_hash"]
        and republication["old_publication_hash"]
        != republication["new_publication_hash"]
        and all(
            republication[field] == controlled_reconstruction[field]
            for field in (
                "old_tbox_hash",
                "new_tbox_hash",
                "old_shacl_hash",
                "new_shacl_hash",
                "old_abox_hash",
                "new_abox_hash",
                "old_publication_hash",
                "new_publication_hash",
                "old_webvowl_hash",
                "new_webvowl_hash",
            )
        )
        and all(
            attestation[field] == republication[field]
            for field in (
                "old_tbox_hash",
                "new_tbox_hash",
                "old_shacl_hash",
                "new_shacl_hash",
                "old_abox_hash",
                "new_abox_hash",
                "old_publication_hash",
                "new_publication_hash",
                "old_webvowl_hash",
                "new_webvowl_hash",
            )
        )
        and all(
            attestation[field] == controlled_reconstruction[field]
            for field in (
                "old_repository_before_hash",
                "old_repository_after_hash",
                "new_repository_expected_hash",
                "new_repository_actual_hash",
            )
        )
        and republication["target_diagnostic_before"]
        == controlled_reconstruction["target_diagnostic_before"]
        and republication["target_diagnostic_after"]
        == controlled_reconstruction["target_diagnostic_after"]
        and attestation["target_diagnostic_before"]
        == controlled_reconstruction["target_diagnostic_before"]
        and attestation["target_diagnostic_after"]
        == controlled_reconstruction["target_diagnostic_after"]
    ):
        raise Phase05ArtifactVerificationError("republication invariant mismatch")

    security = documents["security-summary.json"]
    _exact(
        security,
        {
            "contract_version",
            "test_only",
            "production_authority",
            "unauthorized_amendment_attempts",
            "unauthorized_amendment_blocked",
            "scope_violation_attempts",
            "scope_violation_blocked",
            "semantic_mismatch_attempts",
            "semantic_mismatch_blocked",
            "auto_confirm_attempts",
            "auto_confirm_blocked",
            "direct_rdf_mutation_attempts",
            "direct_rdf_mutation_blocked",
            "graphdb_inplace_mutation_attempts",
            "graphdb_inplace_mutation_blocked",
            "tbox_amendment_attempts",
            "tbox_amendment_blocked",
            "replay_attempts",
            "replay_blocked",
            "status",
        },
        "security summary",
    )
    pairs = (
        ("unauthorized_amendment_attempts", "unauthorized_amendment_blocked"),
        ("scope_violation_attempts", "scope_violation_blocked"),
        ("semantic_mismatch_attempts", "semantic_mismatch_blocked"),
        ("auto_confirm_attempts", "auto_confirm_blocked"),
        ("direct_rdf_mutation_attempts", "direct_rdf_mutation_blocked"),
        ("graphdb_inplace_mutation_attempts", "graphdb_inplace_mutation_blocked"),
        ("tbox_amendment_attempts", "tbox_amendment_blocked"),
        ("replay_attempts", "replay_blocked"),
    )
    expected_security = dict(controlled_reconstruction["security"])
    expected_security["unauthorized_amendment_attempts"] += 1
    try:
        authority.require_request(
            "urn:kg-mnp:test-fixture:phase05:approved-amendment-request:unapproved"
        )
    except AmendmentError as exc:
        if exc.code != AmendmentErrorCode.UNAPPROVED_AMENDMENT:
            raise Phase05ArtifactVerificationError(
                "unexpected out-of-scope amendment rejection"
            ) from exc
        expected_security["unauthorized_amendment_blocked"] += 1
    else:
        raise Phase05ArtifactVerificationError(
            "out-of-scope production amendment was not blocked"
        )
    if not (
        security["test_only"] is True
        and security["production_authority"] is False
        and security["status"] == "PASS"
        and all(
            type(security[attempt]) is int
            and security[attempt] > 0
            and security[attempt] == security[blocked]
            and security[attempt] == expected_security[attempt]
            and security[blocked] == expected_security[blocked]
            and security[attempt] == attestation[attempt]
            and security[blocked] == attestation[blocked]
            for attempt, blocked in pairs
        )
    ):
        raise Phase05ArtifactVerificationError("security attack matrix mismatch")
    return {
        "artifact_files": sorted(FILES),
        "commit_sha": str(expected_commit_sha),
        "production_pending_amendments": authority.production_pending_amendments,
        "controlled_fixture_hash": intake["controlled_fixture_hash"],
        "controlled_reentry_cycles": republication["controlled_reentry_cycles"],
        "controlled_republication_cycles": republication[
            "controlled_republication_cycles"
        ],
        "status": attestation["status"],
    }
