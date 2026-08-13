"""Independent exact-five-file Application Phase04 artifact verifier.

The verifier deliberately accepts only the physical Stage08--Phase03 lineage used
to reconstruct production authority.  A caller-created ``GovernanceAuthority`` is
not an admissible trust root.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .attestation import CATEGORY_FIELDS, aggregate_probes
from .authority_binding import (
    PRODUCTION_AUTHORITY_TYPE,
    load_production_phase03_authority,
)
from .contracts import (
    governance_contract_hash,
    strict_json_file,
    validate_governance_contract,
)
from .validator import validate_governance_workspace_against_authorities

FILES = frozenset(
    {
        "application-phase04-attestation.json",
        "governance-summary.json",
        "state-machine-summary.json",
        "authority-binding.json",
        "security-summary.json",
    }
)
MAX_ARTIFACT_FILE_BYTES = 2 * 1024 * 1024
ABSOLUTE_PATH = re.compile(
    r"(?:(?<![A-Za-z0-9+.-])[A-Za-z]:[\\/]|/(?:home|Users|tmp)/)"
)
SECRET = re.compile(
    r"(?i)(?:GRAPHDB_LICENSE_(?:CONTENT|B64)|authorization\s*[:=]|cookie\s*[:=]|gh[pousr]_[A-Za-z0-9_]{20,}|BEGIN [A-Z ]*PRIVATE KEY)"
)
HASH = re.compile(r"^[0-9a-f]{64}$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
CONTROLLED_PROBE_ID = re.compile(
    r"^urn:kg-mnp:test-fixture:phase04:probe:[0-9a-f]{64}$"
)
AUTHORITY_LAUNDERING_OUTCOMES = {
    "self_minted_phase03_attestation": "AUTHORITY_MISMATCH",
    "synthetic_requirement_snapshot": "AUTHORITY_MISMATCH",
    "synthetic_fact_snapshot": "AUTHORITY_MISMATCH",
    "copied_publication_identity": "AUTHORITY_MISMATCH",
    "copied_repository_hash": "AUTHORITY_MISMATCH",
    "self_consistent_full_rehash": "AUTHORITY_MISMATCH",
    "fixture_to_production_substitution": (
        "TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY"
    ),
}
AUTHORITY_LAUNDERING_ATTACKS = frozenset(AUTHORITY_LAUNDERING_OUTCOMES)


class Phase04ArtifactVerificationError(ValueError):
    """The artifact cannot independently demonstrate Phase04 closure."""


def _exact(value: dict[str, Any], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise Phase04ArtifactVerificationError(f"{label} field set mismatch")


def _documents(directory: Path) -> dict[str, dict[str, Any]]:
    supplied_root = Path(directory)
    if supplied_root.is_symlink():
        raise Phase04ArtifactVerificationError("artifact directory is a symlink")
    try:
        root = supplied_root.resolve(strict=True)
    except OSError as exc:
        raise Phase04ArtifactVerificationError("artifact is unavailable") from exc
    if not root.is_dir():
        raise Phase04ArtifactVerificationError("artifact is not a directory")
    entries = list(root.iterdir())
    if (
        len(entries) != len(FILES)
        or {path.name for path in entries} != FILES
        or any(path.is_symlink() or not path.is_file() for path in entries)
    ):
        raise Phase04ArtifactVerificationError(
            "artifact exact five-file closed set mismatch"
        )
    documents: dict[str, dict[str, Any]] = {}
    for path in entries:
        raw = path.read_bytes()
        if len(raw) > MAX_ARTIFACT_FILE_BYTES:
            raise Phase04ArtifactVerificationError("artifact file is too large")
        text = raw.decode("utf-8", errors="strict")
        if ABSOLUTE_PATH.search(text) or SECRET.search(text):
            raise Phase04ArtifactVerificationError("secret or absolute path detected")
        try:
            documents[path.name] = strict_json_file(path)
        except Exception as exc:
            raise Phase04ArtifactVerificationError(
                "invalid strict JSON artifact"
            ) from exc
    return documents


def _controlled_summary(
    summary: dict[str, Any],
    attestation: dict[str, Any],
    *,
    upstream_phase03_hash: str,
) -> None:
    fields = {
        "fixture_type",
        "test_only",
        "production_authority",
        "controlled_fixture_hash",
        "controlled_fixture_diagnostic_package_hash",
        "controlled_fixture_status",
        "diagnostic_issues",
        "proposals_created",
        "proposals_submitted",
        "reviews_approved",
        "reviews_rejected",
        "reviews_deferred",
        "amendment_requests",
        "status",
    }
    _exact(summary, fields, "controlled scenario summary")
    fixture_hash = summary["controlled_fixture_hash"]
    diagnostic_hash = summary["controlled_fixture_diagnostic_package_hash"]
    if not (
        summary["fixture_type"] == "PHASE04_CONTROLLED_DIAGNOSTIC_FIXTURE"
        and summary["controlled_fixture_status"] == "CONTROLLED_DIAGNOSTIC_FIXTURE"
        and summary["test_only"] is True
        and summary["production_authority"] is False
        and summary["status"] == "PASS"
        and isinstance(fixture_hash, str)
        and HASH.fullmatch(fixture_hash)
        and isinstance(diagnostic_hash, str)
        and HASH.fullmatch(diagnostic_hash)
        and len({fixture_hash, diagnostic_hash, upstream_phase03_hash}) == 3
        and fixture_hash == attestation["controlled_fixture_hash"]
        and diagnostic_hash == attestation["controlled_fixture_diagnostic_package_hash"]
        and summary["controlled_fixture_status"]
        == attestation["controlled_fixture_status"]
    ):
        raise Phase04ArtifactVerificationError(
            "controlled fixture production separation mismatch"
        )
    counts = {
        field: summary[field]
        for field in (
            "diagnostic_issues",
            "proposals_created",
            "proposals_submitted",
            "reviews_approved",
            "reviews_rejected",
            "reviews_deferred",
            "amendment_requests",
        )
    }
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise Phase04ArtifactVerificationError("controlled scenario count mismatch")
    if not (
        counts["diagnostic_issues"] > 0
        and counts["proposals_created"] >= 5
        and counts["proposals_created"] == counts["proposals_submitted"]
        and counts["reviews_approved"] >= 3
        and counts["reviews_rejected"] >= 1
        and counts["reviews_deferred"] >= 1
        and counts["reviews_approved"]
        + counts["reviews_rejected"]
        + counts["reviews_deferred"]
        == counts["proposals_submitted"]
        and counts["amendment_requests"] == counts["reviews_approved"]
    ):
        raise Phase04ArtifactVerificationError(
            "controlled governance aggregation mismatch"
        )


def verify_application_phase04_artifact(
    directory: Path,
    *,
    publication_package_directory: Path,
    publication_attestation_path: Path,
    publication_scenario: str,
    phase01_artifact_directory: Path,
    phase02_artifact_directory: Path,
    phase03_artifact_directory: Path,
    expected_commit_sha: str,
    expected_workspace_hash: str | None = None,
) -> dict[str, Any]:
    """Reconstruct production Phase03 authority, then verify Phase04 evidence.

    Every upstream path is passed to ``load_production_phase03_authority``.  The
    API intentionally has no ``authority`` or ``authority_snapshot`` parameter.
    """

    if not isinstance(expected_commit_sha, str) or not COMMIT_SHA.fullmatch(
        expected_commit_sha
    ):
        raise Phase04ArtifactVerificationError("invalid expected commit SHA")
    if expected_workspace_hash is not None and (
        not isinstance(expected_workspace_hash, str)
        or not HASH.fullmatch(expected_workspace_hash)
    ):
        raise Phase04ArtifactVerificationError("invalid expected workspace hash")

    # This is the verifier's only trust-root construction.  In particular, no
    # caller-supplied GovernanceAuthority can bypass the physical upstream files.
    authority = load_production_phase03_authority(
        publication_package_directory=publication_package_directory,
        publication_attestation_path=publication_attestation_path,
        publication_scenario=publication_scenario,
        phase01_artifact_directory=phase01_artifact_directory,
        phase02_artifact_directory=phase02_artifact_directory,
        phase03_artifact_directory=phase03_artifact_directory,
        expected_commit_sha=expected_commit_sha,
    )
    if authority.authority_type != PRODUCTION_AUTHORITY_TYPE:
        raise Phase04ArtifactVerificationError(
            "TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY"
        )
    documents = _documents(directory)
    attestation = documents["application-phase04-attestation.json"]
    try:
        validate_governance_contract("application-phase04-attestation", attestation)
    except ValueError as exc:
        raise Phase04ArtifactVerificationError("attestation schema failed") from exc
    if attestation["commit_sha"] != expected_commit_sha:
        raise Phase04ArtifactVerificationError("commit binding mismatch")
    if attestation["status"] != "APPLICATION_HUMAN_GOVERNANCE_VERIFIED":
        raise Phase04ArtifactVerificationError("final status is not verified")
    if attestation["governance_contract_hash"] != governance_contract_hash():
        raise Phase04ArtifactVerificationError("governance contract replacement")

    binding = documents["authority-binding.json"]
    _exact(
        binding,
        {"contract_version", *authority.binding, "status"},
        "authority binding",
    )
    expected_binding = {
        "contract_version": "1.0",
        **authority.binding,
        "status": "PASS",
    }
    if binding != expected_binding:
        raise Phase04ArtifactVerificationError("UPSTREAM_PHASE03_AUTHORITY_MISMATCH")
    for field, value in authority.binding.items():
        if attestation[field] != value:
            raise Phase04ArtifactVerificationError(
                "UPSTREAM_PHASE03_AUTHORITY_MISMATCH"
            )
    if (
        attestation["upstream_phase03_issues_total"]
        != authority.upstream_phase03_issues_total
    ):
        raise Phase04ArtifactVerificationError("upstream Phase03 issue count mismatch")

    summary = documents["governance-summary.json"]
    _exact(
        summary,
        {
            "contract_version",
            "production_workspace",
            "production_workspace_hash",
            "production_workspace_revision",
            "production_issues_total",
            "production_proposals_created",
            "production_reviews_approved",
            "production_reviews_rejected",
            "production_reviews_deferred",
            "production_amendment_requests",
            "controlled_scenario_summary",
            "status",
        },
        "governance summary",
    )
    reconstructed = validate_governance_workspace_against_authorities(
        summary["production_workspace"],
        authority,
        expected_workspace_hash=(
            expected_workspace_hash or attestation["production_workspace_hash"]
        ),
    )
    if expected_workspace_hash is not None and (
        attestation["production_workspace_hash"] != expected_workspace_hash
    ):
        raise Phase04ArtifactVerificationError(
            "external workspace head anchor mismatch"
        )
    decisions = reconstructed["review_decisions"]
    production_counts = {
        "production_proposals_created": len(reconstructed["proposals"]),
        "production_reviews_approved": sum(
            decision["decision"] == "APPROVE_FOR_AMENDMENT" for decision in decisions
        ),
        "production_reviews_rejected": sum(
            decision["decision"] == "REJECT" for decision in decisions
        ),
        "production_reviews_deferred": sum(
            decision["decision"] == "DEFER" for decision in decisions
        ),
        "production_amendment_requests": len(
            reconstructed["approved_amendment_requests"]
        ),
    }
    if not (
        summary["contract_version"] == "1.0"
        and summary["status"] == "PASS"
        and summary["production_workspace_hash"]
        == attestation["production_workspace_hash"]
        == reconstructed["workspace_hash"]
        and summary["production_workspace_revision"]
        == attestation["production_workspace_revision"]
        == reconstructed["workspace_revision"]
        and summary["production_issues_total"]
        == attestation["upstream_phase03_issues_total"]
        == authority.upstream_phase03_issues_total
        and all(
            summary[field] == attestation[field] == count
            for field, count in production_counts.items()
        )
    ):
        raise Phase04ArtifactVerificationError("production governance mismatch")
    _controlled_summary(
        summary["controlled_scenario_summary"],
        attestation,
        upstream_phase03_hash=authority.upstream_phase03_diagnostic_package_hash,
    )

    state = documents["state-machine-summary.json"]
    _exact(
        state,
        {
            "contract_version",
            "valid_transitions",
            "invalid_transition_probes",
            "status",
        },
        "state machine",
    )
    if (
        state["contract_version"] != "1.0"
        or state["valid_transitions"]
        != [
            "DRAFT->SUBMITTED",
            "SUBMITTED->APPROVED_FOR_AMENDMENT",
            "SUBMITTED->REJECTED",
            "SUBMITTED->DEFERRED",
        ]
        or state["status"] != "PASS"
    ):
        raise Phase04ArtifactVerificationError("state machine summary mismatch")

    security = documents["security-summary.json"]
    _exact(
        security,
        {
            "contract_version",
            "probe_authority_mode",
            "production_authority",
            "test_only",
            "probes",
            "external_requests",
            "service_workers",
            "status",
        },
        "security summary",
    )
    if not (
        security["contract_version"] == "1.0"
        and security["probe_authority_mode"] == "CONTROLLED_TEST_FIXTURE"
        and security["production_authority"] is False
        and security["test_only"] is True
        and security["external_requests"] == 0
        and security["service_workers"] == 0
        and security["status"] == "PASS"
        and isinstance(security["probes"], list)
    ):
        raise Phase04ArtifactVerificationError("browser/security closure mismatch")
    probes = security["probes"]
    if any(
        not isinstance(probe, dict)
        or not isinstance(probe.get("probe_id"), str)
        or not CONTROLLED_PROBE_ID.fullmatch(probe["probe_id"])
        or probe["probe_id"]
        != "urn:kg-mnp:test-fixture:phase04:probe:"
        + semantic_hash(
            {
                "category": probe.get("category"),
                "attack": probe.get("attack"),
                "expected": probe.get("expected_outcome"),
            }
        )
        or probe.get("blocked") is not True
        or probe.get("status") != "PASS"
        or probe.get("actual_outcome") != probe.get("expected_outcome")
        for probe in probes
    ):
        raise Phase04ArtifactVerificationError(
            "one or more controlled probes did not close"
        )
    try:
        probe_counts = aggregate_probes(probes)
    except ValueError as exc:
        raise Phase04ArtifactVerificationError("invalid controlled probes") from exc
    for attempt, blocked in CATEGORY_FIELDS.values():
        if not (
            probe_counts[attempt]
            == attestation[attempt]
            == probe_counts[blocked]
            == attestation[blocked]
            and probe_counts[attempt] > 0
        ):
            raise Phase04ArtifactVerificationError("probe aggregation mismatch")
    laundering = [
        probe for probe in probes if probe.get("category") == "AUTHORITY_LAUNDERING"
    ]
    if (
        len(laundering) != len(AUTHORITY_LAUNDERING_ATTACKS)
        or {probe.get("attack") for probe in laundering} != AUTHORITY_LAUNDERING_ATTACKS
        or any(
            probe.get("expected_outcome")
            != AUTHORITY_LAUNDERING_OUTCOMES.get(probe.get("attack"))
            or probe.get("actual_outcome")
            != AUTHORITY_LAUNDERING_OUTCOMES.get(probe.get("attack"))
            for probe in laundering
        )
        or not (
            attestation["authority_laundering_attempts"]
            == attestation["authority_laundering_blocked"]
            == len(laundering)
        )
    ):
        raise Phase04ArtifactVerificationError(
            "authority laundering attack matrix did not close"
        )
    if not (
        attestation["controlled_scenarios_total"] == len(probes)
        and attestation["controlled_scenarios_passed"] == len(probes)
    ):
        raise Phase04ArtifactVerificationError(
            "controlled scenario aggregation mismatch"
        )
    if state["invalid_transition_probes"] != [
        probe["probe_id"]
        for probe in probes
        if probe["category"] == "ILLEGAL_TRANSITION"
    ]:
        raise Phase04ArtifactVerificationError("state/security probe mismatch")

    if not (
        attestation["repository_expected_hash"]
        == attestation["repository_before_hash"]
        == attestation["repository_after_hash"]
        == authority.repository_semantic_hash
        and attestation["repository_unchanged"] is True
        and attestation["upstream_phase03_hash_before"]
        == attestation["upstream_phase03_hash_after"]
        == authority.upstream_phase03_diagnostic_package_hash
        and attestation["upstream_phase03_unchanged"] is True
    ):
        raise Phase04ArtifactVerificationError(
            "production authority immutability mismatch"
        )
    return {
        "artifact_files": sorted(FILES),
        "commit_sha": attestation["commit_sha"],
        "production_workspace_hash": reconstructed["workspace_hash"],
        "upstream_phase03_attestation_sha256": (
            authority.upstream_phase03_attestation_sha256
        ),
        "upstream_phase03_diagnostic_package_hash": (
            authority.upstream_phase03_diagnostic_package_hash
        ),
        "controlled_fixture_hash": attestation["controlled_fixture_hash"],
        "controlled_fixture_diagnostic_package_hash": attestation[
            "controlled_fixture_diagnostic_package_hash"
        ],
        "authority_laundering_attempts": attestation["authority_laundering_attempts"],
        "authority_laundering_blocked": attestation["authority_laundering_blocked"],
        "status": "APPLICATION_HUMAN_GOVERNANCE_VERIFIED",
    }
