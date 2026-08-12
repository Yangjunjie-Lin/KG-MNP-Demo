"""Exact binding to an independently reconstructed Phase 03 diagnostic package."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kg_mnp_demo.diagnostics.contracts import (
    strict_json_file,
    validate_diagnostic_contract,
)
from kg_mnp_demo.diagnostics.engine import AuthoritySnapshot
from kg_mnp_demo.diagnostics.validator import (
    validate_diagnostic_package_against_authorities,
)
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

from .errors import GovernanceError, GovernanceErrorCode


def _document_and_hash(
    value: Mapping[str, Any] | Path | str,
) -> tuple[dict[str, Any], str]:
    if isinstance(value, (Path, str)):
        path = Path(value)
        raw = path.read_bytes()
        document = strict_json_file(path)
    else:
        document = deepcopy(dict(value))
        raw = canonical_json_bytes(document) + b"\n"
    return document, hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class GovernanceAuthority:
    publication_id: str
    publication_semantic_hash: str
    repository_semantic_hash: str
    phase03_attestation_hash: str
    diagnostic_package_hash: str
    issues: Mapping[str, Mapping[str, Any]]

    @property
    def binding(self) -> dict[str, str]:
        return {
            "publication_id": self.publication_id,
            "publication_semantic_hash": self.publication_semantic_hash,
            "repository_semantic_hash": self.repository_semantic_hash,
            "phase03_attestation_hash": self.phase03_attestation_hash,
            "diagnostic_package_hash": self.diagnostic_package_hash,
        }

    def require_issue(
        self, diagnostic_id: str, diagnostic_basis_hash: str | None = None
    ) -> dict[str, Any]:
        issue = self.issues.get(diagnostic_id)
        if issue is None:
            raise GovernanceError(GovernanceErrorCode.UNKNOWN_DIAGNOSTIC)
        if (
            diagnostic_basis_hash is not None
            and issue.get("diagnostic_basis_hash") != diagnostic_basis_hash
        ):
            raise GovernanceError(GovernanceErrorCode.STALE_DIAGNOSTIC_BINDING)
        return deepcopy(dict(issue))

    def assert_same_current_authority(self, expected: Mapping[str, Any]) -> None:
        if any(expected.get(key) != value for key, value in self.binding.items()):
            raise GovernanceError(GovernanceErrorCode.STALE_DIAGNOSTIC_BINDING)


def load_verified_phase03_authority(
    *,
    diagnostic_package: Mapping[str, Any] | Path | str,
    phase03_attestation: Mapping[str, Any] | Path | str,
    authority_snapshot: AuthoritySnapshot | Mapping[str, Any] | Path | str,
) -> GovernanceAuthority:
    """Rebuild Phase03 before exposing any diagnostic as a governance target."""

    try:
        package_value, _ = _document_and_hash(diagnostic_package)
        attestation, attestation_hash = _document_and_hash(phase03_attestation)
        validate_diagnostic_contract("diagnostic-attestation", attestation)
        reconstruction = validate_diagnostic_package_against_authorities(
            package_value, authority_snapshot
        )
        bindings = package_value["authority_bindings"]
        expected = (
            (attestation.get("status"), "APPLICATION_DIAGNOSTICS_VERIFIED"),
            (
                attestation.get("diagnostic_package_hash"),
                reconstruction["package_semantic_hash"],
            ),
            (attestation.get("publication_id"), bindings["publication_id"]),
            (
                attestation.get("publication_semantic_hash"),
                bindings["publication_semantic_hash"],
            ),
            (
                attestation.get("repository_expected_hash"),
                bindings["repository_semantic_hash"],
            ),
            (
                attestation.get("repository_before_hash"),
                bindings["repository_semantic_hash"],
            ),
            (
                attestation.get("repository_after_hash"),
                bindings["repository_semantic_hash"],
            ),
            (attestation.get("repository_unchanged"), True),
        )
        if any(left != right for left, right in expected):
            raise ValueError("Phase03 attestation/package authority mismatch")
        issues = {
            issue["diagnostic_id"]: deepcopy(issue) for issue in package_value["issues"]
        }
        return GovernanceAuthority(
            publication_id=bindings["publication_id"],
            publication_semantic_hash=bindings["publication_semantic_hash"],
            repository_semantic_hash=bindings["repository_semantic_hash"],
            phase03_attestation_hash=attestation_hash,
            diagnostic_package_hash=reconstruction["package_semantic_hash"],
            issues=issues,
        )
    except GovernanceError:
        raise
    except Exception as exc:
        raise GovernanceError(
            GovernanceErrorCode.AUTHORITY_MISMATCH,
            "Phase03 authority reconstruction failed",
        ) from exc
