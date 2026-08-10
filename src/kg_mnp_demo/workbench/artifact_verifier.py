"""Independent verifier for the five-file Phase 02 CI artifact."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .contracts import strict_json_file, validate_workbench_contract


ARTIFACT_FILES = frozenset(
    {
        "application-phase02-attestation.json",
        "browser-smoke.json",
        "security-summary.json",
        "binding-summary.json",
        "graphdb-before-after.json",
    }
)
MAX_FILE_BYTES = 2 * 1024 * 1024
SENSITIVE_KEY_MARKERS = (
    "authorization",
    "cookie",
    "credential",
    "environment",
    "license",
    "password",
    "secret",
    "token",
)
ABSOLUTE_PATH = re.compile(
    r"(?i)(?:[a-z]:[\\/]|/(?:home|users|opt|var|tmp)/[^/\s]+)"
)


class WorkbenchArtifactVerificationError(ValueError):
    pass


def _scan(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
            if any(marker in normalized for marker in SENSITIVE_KEY_MARKERS):
                raise WorkbenchArtifactVerificationError("sensitive JSON key")
            _scan(child)
    elif isinstance(value, list):
        for child in value:
            _scan(child)
    elif isinstance(value, str) and (
        ABSOLUTE_PATH.search(value)
        or "HOME=" in value
        or "PATH=" in value
    ):
        raise WorkbenchArtifactVerificationError("sensitive JSON value")


def _documents(directory: Path) -> dict[str, dict[str, Any]]:
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise WorkbenchArtifactVerificationError("artifact directory invalid")
    entries = list(root.iterdir())
    if (
        len(entries) != len(ARTIFACT_FILES)
        or {path.name for path in entries} != ARTIFACT_FILES
        or any(path.is_symlink() or not path.is_file() for path in entries)
    ):
        raise WorkbenchArtifactVerificationError("artifact closed set mismatch")
    documents: dict[str, dict[str, Any]] = {}
    for name in sorted(ARTIFACT_FILES):
        path = root / name
        if not 0 < path.stat().st_size <= MAX_FILE_BYTES:
            raise WorkbenchArtifactVerificationError("artifact size invalid")
        try:
            document = strict_json_file(path)
        except Exception as exc:
            raise WorkbenchArtifactVerificationError("artifact JSON invalid") from exc
        _scan(document)
        documents[name] = document
    return documents


def verify_application_phase02_artifact(directory: Path) -> dict[str, Any]:
    documents = _documents(directory)
    attestation = documents["application-phase02-attestation.json"]
    try:
        validate_workbench_contract("attestation", attestation)
    except Exception as exc:
        raise WorkbenchArtifactVerificationError(
            "Phase 02 attestation schema failed"
        ) from exc
    if (
        attestation["xss_attack_count"] != attestation["xss_attack_blocked"]
        or attestation["relay_attack_count"]
        != attestation["relay_attack_blocked"]
        or attestation["authority_tamper_attack_count"]
        != attestation["authority_tamper_attack_blocked"]
        or attestation["direct_graphdb_access_attempt_count"]
        != attestation["direct_graphdb_access_blocked_count"]
        or not (
            attestation["repository_hash_expected"]
            == attestation["repository_hash_before"]
            == attestation["repository_hash_after"]
        )
    ):
        raise WorkbenchArtifactVerificationError("attestation closure failed")
    binding = documents["binding-summary.json"]
    before_after = documents["graphdb-before-after.json"]
    browser = documents["browser-smoke.json"]
    security = documents["security-summary.json"]
    if (
        binding.get("publication_id") != attestation["publication_id"]
        or binding.get("publication_semantic_hash")
        != attestation["publication_semantic_hash"]
        or binding.get("phase01_attestation_hash")
        != attestation["phase01_attestation_hash"]
        or binding.get("query_registry_hash")
        != attestation["query_registry_hash"]
        or binding.get("status") != "PASS"
    ):
        raise WorkbenchArtifactVerificationError("binding summary mismatch")
    if (
        before_after.get("expected") != attestation["repository_hash_expected"]
        or before_after.get("before") != attestation["repository_hash_before"]
        or before_after.get("after") != attestation["repository_hash_after"]
        or before_after.get("repository_unchanged") is not True
        or before_after.get("status") != "PASS"
    ):
        raise WorkbenchArtifactVerificationError("repository evidence mismatch")
    if (
        browser.get("status") != "PASS"
        or browser.get("external_requests") != []
        or browser.get("service_worker_count") != 0
        or browser.get("golden_scenario_passed") != 4
    ):
        raise WorkbenchArtifactVerificationError("browser evidence mismatch")
    if (
        security.get("status") != "PASS"
        or security.get("xss_attack_count") != attestation["xss_attack_count"]
        or security.get("xss_attack_blocked") != attestation["xss_attack_blocked"]
        or security.get("relay_attack_count")
        != attestation["relay_attack_count"]
        or security.get("relay_attack_blocked")
        != attestation["relay_attack_blocked"]
    ):
        raise WorkbenchArtifactVerificationError("security summary mismatch")
    return {
        "status": "APPLICATION_WORKBENCH_VERIFIED",
        "commit_sha": attestation["commit_sha"],
        "publication_id": attestation["publication_id"],
        "artifact_files": sorted(ARTIFACT_FILES),
    }
