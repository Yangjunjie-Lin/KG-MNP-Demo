"""Independent exact-five-file Application Phase04 artifact verifier."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .attestation import CATEGORY_FIELDS, aggregate_probes
from .authority_binding import GovernanceAuthority
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
ABSOLUTE_PATH = re.compile(
    r"(?:(?<![A-Za-z0-9+.-])[A-Za-z]:[\\/]|/(?:home|Users|tmp)/)"
)
SECRET = re.compile(
    r"(?i)(?:GRAPHDB_LICENSE_(?:CONTENT|B64)|authorization\s*[:=]|cookie\s*[:=]|gh[pousr]_[A-Za-z0-9_]{20,}|BEGIN [A-Z ]*PRIVATE KEY)"
)


class Phase04ArtifactVerificationError(ValueError):
    pass


def _exact(value: dict[str, Any], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise Phase04ArtifactVerificationError(f"{label} field set mismatch")


def verify_application_phase04_artifact(
    directory: Path,
    *,
    authority: GovernanceAuthority,
    expected_commit_sha: str | None = None,
    expected_workspace_hash: str | None = None,
) -> dict[str, Any]:
    root = Path(directory).resolve(strict=True)
    paths = [path for path in root.rglob("*") if path.is_file() or path.is_symlink()]
    actual = {path.relative_to(root).as_posix() for path in paths}
    if actual != FILES or any(path.is_symlink() for path in paths):
        raise Phase04ArtifactVerificationError(
            "artifact exact five-file closed set mismatch"
        )
    documents: dict[str, dict[str, Any]] = {}
    for path in paths:
        raw = path.read_text(encoding="utf-8")
        if ABSOLUTE_PATH.search(raw) or SECRET.search(raw):
            raise Phase04ArtifactVerificationError("secret or absolute path detected")
        try:
            documents[path.name] = strict_json_file(path)
        except Exception as exc:
            raise Phase04ArtifactVerificationError(
                "invalid strict JSON artifact"
            ) from exc
    attestation = documents["application-phase04-attestation.json"]
    validate_governance_contract("application-phase04-attestation", attestation)
    if (
        expected_commit_sha is not None
        and attestation["commit_sha"] != expected_commit_sha
    ):
        raise Phase04ArtifactVerificationError("commit binding mismatch")
    if attestation["status"] != "APPLICATION_HUMAN_GOVERNANCE_VERIFIED":
        raise Phase04ArtifactVerificationError("final status is not verified")
    if attestation["governance_contract_hash"] != governance_contract_hash():
        raise Phase04ArtifactVerificationError("governance contract replacement")
    binding = documents["authority-binding.json"]
    _exact(
        binding, {"contract_version", *authority.binding, "status"}, "authority binding"
    )
    if binding != {"contract_version": "1.0", **authority.binding, "status": "PASS"}:
        raise Phase04ArtifactVerificationError("authority identity mismatch")
    for field, value in authority.binding.items():
        if attestation[field] != value:
            raise Phase04ArtifactVerificationError("attestation authority mismatch")
    summary = documents["governance-summary.json"]
    _exact(
        summary,
        {
            "contract_version",
            "workspace",
            "workspace_hash",
            "workspace_revision",
            "proposals_created",
            "proposals_submitted",
            "reviews_approved",
            "reviews_rejected",
            "reviews_deferred",
            "approved_amendment_requests",
            "status",
        },
        "governance summary",
    )
    reconstructed = validate_governance_workspace_against_authorities(
        summary["workspace"],
        authority,
        expected_workspace_hash=(
            expected_workspace_hash or attestation["governance_workspace_hash"]
        ),
    )
    if (
        expected_workspace_hash is not None
        and attestation["governance_workspace_hash"] != expected_workspace_hash
    ):
        raise Phase04ArtifactVerificationError(
            "external workspace head anchor mismatch"
        )
    if (
        summary["workspace_hash"] != reconstructed["workspace_hash"]
        or summary["workspace_revision"] != reconstructed["workspace_revision"]
    ):
        raise Phase04ArtifactVerificationError("workspace summary mismatch")
    derived_counts = {
        "proposals_created": len(reconstructed["proposals"]),
        "proposals_submitted": sum(
            p["status"] != "DRAFT" for p in reconstructed["proposals"]
        ),
        "reviews_approved": sum(
            d["decision"] == "APPROVE_FOR_AMENDMENT"
            for d in reconstructed["review_decisions"]
        ),
        "reviews_rejected": sum(
            d["decision"] == "REJECT" for d in reconstructed["review_decisions"]
        ),
        "reviews_deferred": sum(
            d["decision"] == "DEFER" for d in reconstructed["review_decisions"]
        ),
        "approved_amendment_requests": len(
            reconstructed["approved_amendment_requests"]
        ),
    }
    if (
        any(
            summary[key] != value or attestation[key] != value
            for key, value in derived_counts.items()
        )
        or summary["status"] != "PASS"
    ):
        raise Phase04ArtifactVerificationError("governance aggregation mismatch")
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
        state["valid_transitions"]
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
            "probes",
            "external_requests",
            "service_workers",
            "status",
        },
        "security summary",
    )
    probe_counts = aggregate_probes(security["probes"])
    if any(
        probe["blocked"] is not True
        or probe["status"] != "PASS"
        or probe["actual_outcome"] != probe["expected_outcome"]
        for probe in security["probes"]
    ):
        raise Phase04ArtifactVerificationError(
            "one or more executed probes did not close"
        )
    for attempt, blocked in CATEGORY_FIELDS.values():
        if (
            probe_counts[attempt] != attestation[attempt]
            or probe_counts[blocked] != attestation[blocked]
        ):
            raise Phase04ArtifactVerificationError("probe aggregation mismatch")
    if (
        security["external_requests"] != 0
        or security["service_workers"] != 0
        or security["status"] != "PASS"
    ):
        raise Phase04ArtifactVerificationError("browser/security closure mismatch")
    if state["invalid_transition_probes"] != [
        p["probe_id"]
        for p in security["probes"]
        if p["category"] == "ILLEGAL_TRANSITION"
    ]:
        raise Phase04ArtifactVerificationError("state/security probe mismatch")
    if not (
        attestation["repository_expected_hash"]
        == attestation["repository_before_hash"]
        == attestation["repository_after_hash"]
        == authority.repository_semantic_hash
        and attestation["repository_unchanged"] is True
        and attestation["diagnostic_hash_before"]
        == attestation["diagnostic_hash_after"]
        == authority.diagnostic_package_hash
        and attestation["diagnostic_unchanged"] is True
    ):
        raise Phase04ArtifactVerificationError("authority immutability mismatch")
    return {
        "artifact_files": sorted(FILES),
        "commit_sha": attestation["commit_sha"],
        "workspace_hash": reconstructed["workspace_hash"],
        "status": "APPLICATION_HUMAN_GOVERNANCE_VERIFIED",
    }
