"""Independent verifier for the exact five-file Phase 03 CI artifact."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from .contracts import strict_json_bytes, validate_diagnostic_contract
from .policy import diagnostic_policy_hash


ARTIFACT_FILES = frozenset(
    {
        "application-phase03-attestation.json",
        "diagnostics-summary.json",
        "diagnostic-determinism.json",
        "authority-binding.json",
        "security-summary.json",
    }
)
MAX_ARTIFACT_FILE_BYTES = 2 * 1024 * 1024
_SENSITIVE_KEY_MARKERS = (
    "authorization",
    "cookie",
    "credential",
    "password",
    "privatekey",
    "rawenv",
    "secret",
    "token",
)
_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"(?i)\b(?:authorization|cookie|set-cookie)\s*[:=]"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,})\b"),
)
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


class DiagnosticArtifactVerificationError(ValueError):
    """The artifact cannot independently demonstrate Phase 03 closure."""


def _scan(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
            if any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS):
                raise DiagnosticArtifactVerificationError("sensitive JSON key")
            _scan(child)
    elif isinstance(value, list):
        for child in value:
            _scan(child)
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in _SENSITIVE_VALUE_PATTERNS):
            raise DiagnosticArtifactVerificationError("sensitive JSON value")
        if _WINDOWS_ABSOLUTE.match(value) or (
            value.startswith("/") and not value.startswith("//")
        ):
            raise DiagnosticArtifactVerificationError("absolute filesystem path")
        pure = PurePosixPath(value.replace("\\", "/"))
        if ".." in pure.parts:
            raise DiagnosticArtifactVerificationError("path traversal value")


def _documents(directory: Path) -> dict[str, dict[str, Any]]:
    root = Path(directory)
    if root.is_symlink():
        raise DiagnosticArtifactVerificationError("artifact directory is a symlink")
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise DiagnosticArtifactVerificationError("artifact is unavailable") from exc
    if not root.is_dir():
        raise DiagnosticArtifactVerificationError("artifact is not a directory")
    entries = list(root.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in entries):
        raise DiagnosticArtifactVerificationError("artifact contains unsafe entry")
    if {path.name for path in entries} != ARTIFACT_FILES or len(entries) != len(ARTIFACT_FILES):
        raise DiagnosticArtifactVerificationError("artifact closed set mismatch")
    documents: dict[str, dict[str, Any]] = {}
    for path in entries:
        raw = path.read_bytes()
        if len(raw) > MAX_ARTIFACT_FILE_BYTES:
            raise DiagnosticArtifactVerificationError("artifact file is too large")
        try:
            value = strict_json_bytes(raw)
        except ValueError as exc:
            raise DiagnosticArtifactVerificationError("artifact JSON is invalid") from exc
        if not isinstance(value, dict):
            raise DiagnosticArtifactVerificationError("artifact JSON root is not an object")
        _scan(value)
        documents[path.name] = value
    return documents


def _exact(value: dict[str, Any], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise DiagnosticArtifactVerificationError(f"{label} field set mismatch")


def verify_application_phase03_artifact(
    directory: Path,
    *,
    expected_commit_sha: str | None = None,
) -> dict[str, Any]:
    documents = _documents(directory)
    attestation = documents["application-phase03-attestation.json"]
    try:
        validate_diagnostic_contract("diagnostic-attestation", attestation)
    except ValueError as exc:
        raise DiagnosticArtifactVerificationError("attestation schema failed") from exc
    if attestation["status"] != "APPLICATION_DIAGNOSTICS_VERIFIED":
        raise DiagnosticArtifactVerificationError("Phase 03 status is not verified")
    if expected_commit_sha is not None and attestation["commit_sha"] != expected_commit_sha:
        raise DiagnosticArtifactVerificationError("commit SHA binding mismatch")
    binding = documents["authority-binding.json"]
    _exact(
        binding,
        {
            "contract_version",
            "publication_id",
            "publication_semantic_hash",
            "phase01_attestation_hash",
            "phase02_attestation_hash",
            "query_registry_hash",
            "repository_semantic_hash",
            "diagnostic_policy_hash",
            "status",
        },
        "authority binding",
    )
    if binding["contract_version"] != "1.0" or binding["status"] != "PASS":
        raise DiagnosticArtifactVerificationError("authority binding did not pass")
    binding_pairs = {
        "publication_id": "publication_id",
        "publication_semantic_hash": "publication_semantic_hash",
        "phase01_attestation_hash": "phase01_attestation_hash",
        "phase02_attestation_hash": "phase02_attestation_hash",
        "query_registry_hash": "query_registry_hash",
        "repository_semantic_hash": "repository_expected_hash",
        "diagnostic_policy_hash": "diagnostic_policy_hash",
    }
    if any(binding[left] != attestation[right] for left, right in binding_pairs.items()):
        raise DiagnosticArtifactVerificationError("authority identity mismatch")
    if binding["diagnostic_policy_hash"] != diagnostic_policy_hash():
        raise DiagnosticArtifactVerificationError("diagnostic policy replacement")
    summary = documents["diagnostics-summary.json"]
    _exact(
        summary,
        {
            "contract_version",
            "diagnostic_package_hash",
            "issues_total",
            "issues_by_classification",
            "requirements_evaluated",
            "constraints_evaluated",
            "status",
        },
        "diagnostics summary",
    )
    if (
        summary["status"] != "PASS"
        or summary["diagnostic_package_hash"] != attestation["diagnostic_package_hash"]
        or summary["issues_total"] != attestation["issues_total"]
        or summary["issues_by_classification"] != attestation["issues_by_classification"]
        or summary["requirements_evaluated"] != attestation["requirements_evaluated"]
        or summary["constraints_evaluated"] != attestation["constraints_evaluated"]
    ):
        raise DiagnosticArtifactVerificationError("diagnostics summary mismatch")
    determinism = documents["diagnostic-determinism.json"]
    _exact(
        determinism,
        {
            "contract_version",
            "diagnostic_package_hash",
            "determinism_runs",
            "canonical_hashes",
            "determinism_passed",
            "permutation_attacks",
            "permutation_passed",
            "status",
        },
        "determinism",
    )
    hashes = determinism["canonical_hashes"]
    if (
        determinism["status"] != "PASS"
        or determinism["diagnostic_package_hash"] != attestation["diagnostic_package_hash"]
        or determinism["determinism_runs"] != attestation["determinism_runs"]
        or determinism["determinism_passed"] is not True
        or determinism["permutation_attacks"] != attestation["permutation_attacks"]
        or determinism["permutation_passed"] is not True
        or not isinstance(hashes, list)
        or len(hashes) != determinism["determinism_runs"]
        or set(hashes) != {attestation["diagnostic_package_hash"]}
    ):
        raise DiagnosticArtifactVerificationError("determinism evidence mismatch")
    security = documents["security-summary.json"]
    security_fields = {
        "contract_version",
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
        "status",
    }
    _exact(security, security_fields, "security summary")
    for field in security_fields - {"contract_version", "status"}:
        if security[field] != attestation[field]:
            raise DiagnosticArtifactVerificationError("security evidence mismatch")
    if security["status"] != "PASS":
        raise DiagnosticArtifactVerificationError("security evidence did not pass")
    if not (
        attestation["repository_expected_hash"]
        == attestation["repository_before_hash"]
        == attestation["repository_after_hash"]
        and attestation["repository_unchanged"] is True
    ):
        raise DiagnosticArtifactVerificationError("repository identity changed")
    return {
        "commit_sha": attestation["commit_sha"],
        "diagnostic_package_hash": attestation["diagnostic_package_hash"],
        "issues_total": attestation["issues_total"],
        "status": "APPLICATION_DIAGNOSTICS_VERIFIED",
    }


verify_diagnostics_artifact = verify_application_phase03_artifact
