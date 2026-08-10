"""Independent verification of the closed Application Phase 01 CI artifact."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .contracts import validate_application_contract
from .query_registry import QueryRegistry


ARTIFACT_FILES = frozenset(
    {
        "application-attestation.json",
        "query-registry-manifest.json",
        "golden-query-summary.json",
        "security-summary.json",
        "graphdb-before-after.json",
    }
)
MAX_ARTIFACT_FILE_BYTES = 2 * 1024 * 1024
PUBLICATION_SCENARIOS = frozenset(
    {
        "full-confirmation",
        "modified-confirmation",
        "rejection",
        "issue-resolution",
    }
)

_FORBIDDEN_KEY_MARKERS = (
    "authorization",
    "cookie",
    "credential",
    "password",
    "privatekey",
    "rawenv",
    "secret",
    "token",
)
_FORBIDDEN_KEYS = frozenset(
    {
        "auths",
        "clientsecret",
        "credhelpers",
        "credsstore",
        "dockerconfig",
        "environment",
        "env",
        "graphdblicenseb64",
        "graphdblicensecontent",
        "identitytoken",
        "licensecontent",
        "licensepath",
        "privatekey",
    }
)
_FORBIDDEN_VALUE_PATTERNS = (
    re.compile(
        r"(?i)\b(?:authorization|proxy-authorization|cookie|set-cookie)\s*[:=]"
    ),
    re.compile(r"(?i)\bgraphdb_license_(?:content|b64)\s*="),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,})\b"),
)


class ArtifactVerificationError(ValueError):
    """Raised when the CI artifact cannot independently prove closure."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    folded: set[str] = set()
    for key, value in pairs:
        marker = key.casefold()
        if marker in folded:
            raise ArtifactVerificationError("duplicate JSON key")
        folded.add(marker)
        result[key] = value
    return result


def _scan_sensitive(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
            if normalized in _FORBIDDEN_KEYS or any(
                marker in normalized for marker in _FORBIDDEN_KEY_MARKERS
            ):
                raise ArtifactVerificationError("sensitive JSON key")
            _scan_sensitive(child)
    elif isinstance(value, list):
        for child in value:
            _scan_sensitive(child)
    elif isinstance(value, str) and any(
        pattern.search(value) for pattern in _FORBIDDEN_VALUE_PATTERNS
    ):
        raise ArtifactVerificationError("sensitive JSON value")


def _load_documents(directory: Path) -> dict[str, dict[str, Any]]:
    root = Path(directory)
    if root.is_symlink():
        raise ArtifactVerificationError("artifact directory must not be a symlink")
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise ArtifactVerificationError("artifact directory is unavailable") from exc
    if not root.is_dir():
        raise ArtifactVerificationError("artifact path is not a directory")
    entries = list(root.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in entries):
        raise ArtifactVerificationError("artifact must contain only regular files")
    names = {path.name for path in entries}
    if names != ARTIFACT_FILES or len(entries) != len(ARTIFACT_FILES):
        raise ArtifactVerificationError("application artifact closed set mismatch")

    documents: dict[str, dict[str, Any]] = {}
    for name in sorted(ARTIFACT_FILES):
        path = root / name
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ArtifactVerificationError("artifact file is unreadable") from exc
        if not raw or len(raw) > MAX_ARTIFACT_FILE_BYTES:
            raise ArtifactVerificationError("artifact file size is invalid")
        try:
            value = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=lambda _value: (_ for _ in ()).throw(
                    ArtifactVerificationError("non-finite JSON number")
                ),
            )
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ArtifactVerificationError("artifact file is not strict JSON") from exc
        if not isinstance(value, dict):
            raise ArtifactVerificationError("artifact JSON root must be an object")
        _scan_sensitive(value)
        documents[name] = value
    return documents


def _require_keys(document: dict[str, Any], expected: set[str], label: str) -> None:
    if set(document) != expected:
        raise ArtifactVerificationError(f"{label} field set mismatch")


def verify_application_phase01_artifact(directory: Path) -> dict[str, Any]:
    """Verify the five-file artifact without trusting its asserted status."""

    documents = _load_documents(directory)
    attestation = documents["application-attestation.json"]
    try:
        validate_application_contract("application-phase01-attestation", attestation)
    except Exception as exc:
        raise ArtifactVerificationError("application attestation schema failed") from exc
    if attestation["status"] != "APPLICATION_READONLY_VERIFIED":
        raise ArtifactVerificationError("application attestation is not verified")
    if attestation["publication_id"] != (
        "urn:kg-mnp:e2e-publication:" + attestation["publication_semantic_hash"]
    ):
        raise ArtifactVerificationError("publication identity mismatch")

    authority = attestation["publication_authority_reconstruction"]
    if (
        set(authority) != {"status", "scenario", "publication_id"}
        or authority["status"] != "PASS"
        or authority["scenario"] not in PUBLICATION_SCENARIOS
        or authority["publication_id"] != attestation["publication_id"]
    ):
        raise ArtifactVerificationError("publication authority reconstruction failed")

    expected_hash = attestation["expected_graphdb_semantic_hash"]
    before_hash = attestation["live_graphdb_semantic_hash_before"]
    after_hash = attestation["live_graphdb_semantic_hash_after"]
    if (
        expected_hash != before_hash
        or expected_hash != after_hash
        or attestation["repository_unchanged"] is not True
        or attestation["repository_semantic_identity_verified"] is not True
    ):
        raise ArtifactVerificationError("live GraphDB semantic identity mismatch")

    registry = documents["query-registry-manifest.json"]
    try:
        expected_registry = QueryRegistry.load().manifest()
    except Exception as exc:
        raise ArtifactVerificationError("source query registry is unavailable") from exc
    if registry != expected_registry:
        raise ArtifactVerificationError("query registry manifest mismatch")
    if registry.get("query_registry_hash") != attestation["query_registry_hash"]:
        raise ArtifactVerificationError("query registry hash mismatch")

    golden = documents["golden-query-summary.json"]
    _require_keys(
        golden,
        {
            "contract_version",
            "publication_id",
            "query_registry_hash",
            "golden_query_count",
            "golden_query_passed",
            "status",
        },
        "golden query summary",
    )
    if golden != {
        "contract_version": "1.0",
        "publication_id": attestation["publication_id"],
        "query_registry_hash": attestation["query_registry_hash"],
        "golden_query_count": attestation["golden_query_count"],
        "golden_query_passed": attestation["golden_query_passed"],
        "status": "PASS",
    }:
        raise ArtifactVerificationError("golden query summary mismatch")
    if golden["golden_query_count"] != golden["golden_query_passed"]:
        raise ArtifactVerificationError("golden queries are incomplete")

    security = documents["security-summary.json"]
    _require_keys(
        security,
        {
            "contract_version",
            "publication_id",
            "repository_id",
            "mutation_attack_count",
            "mutation_attack_blocked",
            "live_repository_tamper_attack_count",
            "live_repository_tamper_attack_blocked",
            "status",
        },
        "security summary",
    )
    if security != {
        "contract_version": "1.0",
        "publication_id": attestation["publication_id"],
        "repository_id": attestation["repository_id"],
        "mutation_attack_count": attestation["mutation_attack_count"],
        "mutation_attack_blocked": attestation["mutation_attack_blocked"],
        "live_repository_tamper_attack_count": attestation[
            "live_repository_tamper_attack_count"
        ],
        "live_repository_tamper_attack_blocked": attestation[
            "live_repository_tamper_attack_blocked"
        ],
        "status": "PASS",
    }:
        raise ArtifactVerificationError("security summary mismatch")
    if (
        security["mutation_attack_count"] != security["mutation_attack_blocked"]
        or security["live_repository_tamper_attack_count"]
        != security["live_repository_tamper_attack_blocked"]
    ):
        raise ArtifactVerificationError("security attacks were not all blocked")

    before_after = documents["graphdb-before-after.json"]
    _require_keys(
        before_after,
        {
            "contract_version",
            "publication_id",
            "repository_id",
            "expected_graphdb_semantic_hash",
            "live_graphdb_semantic_hash_before",
            "live_graphdb_semantic_hash_after",
            "publication_authority_reconstruction",
            "repository_semantic_identity_verified",
            "repository_unchanged",
        },
        "GraphDB before/after evidence",
    )
    if before_after != {
        "contract_version": "1.0",
        "publication_id": attestation["publication_id"],
        "repository_id": attestation["repository_id"],
        "expected_graphdb_semantic_hash": expected_hash,
        "live_graphdb_semantic_hash_before": before_hash,
        "live_graphdb_semantic_hash_after": after_hash,
        "publication_authority_reconstruction": authority,
        "repository_semantic_identity_verified": True,
        "repository_unchanged": True,
    }:
        raise ArtifactVerificationError("GraphDB before/after evidence mismatch")

    return {
        "status": "APPLICATION_READONLY_VERIFIED",
        "publication_id": attestation["publication_id"],
        "repository_id": attestation["repository_id"],
        "expected_graphdb_semantic_hash": expected_hash,
        "live_graphdb_semantic_hash_before": before_hash,
        "live_graphdb_semantic_hash_after": after_hash,
        "publication_authority_reconstruction": authority,
        "artifact_files": sorted(ARTIFACT_FILES),
    }
