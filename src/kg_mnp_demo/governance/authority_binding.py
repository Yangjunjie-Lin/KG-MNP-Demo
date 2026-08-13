"""Closed production binding to the exact verified Phase 03 artifact lineage."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from kg_mnp_demo.diagnostics.artifact_verifier import (
    verify_application_phase03_artifact,
)
from kg_mnp_demo.diagnostics.authority_loader import (
    load_verified_authority_snapshot,
)
from kg_mnp_demo.diagnostics.contracts import strict_json_bytes
from kg_mnp_demo.diagnostics.engine import reconstruct_diagnostics
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.workbench.artifact_verifier import (
    verify_application_phase02_artifact,
)

from .errors import GovernanceError, GovernanceErrorCode

PRODUCTION_AUTHORITY_TYPE = "PRODUCTION_EXACT_PHASE03"
CONTROLLED_HARNESS_AUTHORITY_TYPE = "CONTROLLED_TEST_HARNESS"
_HASH = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_TEST_FIXTURE_MARKERS = {
    "PHASE04_CONTROLLED_DIAGNOSTIC_FIXTURE",
    "CONTROLLED_DIAGNOSTIC_FIXTURE",
}


@dataclass(frozen=True, slots=True)
class _ProductionAuthoritySource:
    """Exact artifact locations needed to repeat production verification.

    This descriptor is intentionally not a credential.  It may be inspected or
    copied by a caller: production acceptance depends on re-verifying the files
    it names and comparing the reconstructed authority, never on object identity
    or a secret in-process capability.
    """

    publication_package_directory: Path
    publication_attestation_path: Path
    phase01_artifact_directory: Path
    phase02_artifact_directory: Path
    phase03_artifact_directory: Path
    expected_commit_sha: str
    publication_scenario: str

    def loader_arguments(self) -> dict[str, Any]:
        return {
            "publication_package_directory": self.publication_package_directory,
            "publication_attestation_path": self.publication_attestation_path,
            "phase01_artifact_directory": self.phase01_artifact_directory,
            "phase02_artifact_directory": self.phase02_artifact_directory,
            "phase03_artifact_directory": self.phase03_artifact_directory,
            "expected_commit_sha": self.expected_commit_sha,
            "publication_scenario": self.publication_scenario,
        }


def _fixture_marker(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _reject_test_fixture(value: Any) -> None:
    """Recognize the public fixture contract before attempting path coercion."""

    fixture_type = _fixture_marker(value, "fixture_type")
    status = _fixture_marker(value, "status")
    if (
        fixture_type in _TEST_FIXTURE_MARKERS
        or status in _TEST_FIXTURE_MARKERS
        or _fixture_marker(value, "test_only") is True
        or _fixture_marker(value, "production_authority") is False
    ):
        raise GovernanceError(
            GovernanceErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY
        )


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def _artifact_tree_digest(path: Path) -> str:
    """Freeze a regular-file tree without following links or special entries."""

    supplied = Path(path)
    if supplied.is_symlink():
        raise ValueError("upstream artifact tree is unsafe")
    root = supplied.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("upstream artifact tree is unsafe")
    records: list[dict[str, str]] = []
    for entry in root.rglob("*"):
        if entry.is_symlink():
            raise ValueError("upstream artifact tree contains an unsafe entry")
        if entry.is_dir():
            continue
        if not entry.is_file():
            raise ValueError("upstream artifact tree contains an unsafe entry")
        records.append(
            {
                "relative_path": entry.relative_to(root).as_posix(),
                "byte_sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
            }
        )
    content = sorted(records, key=lambda row: row["relative_path"])
    return hashlib.sha256(canonical_json_bytes(content)).hexdigest()


@dataclass(frozen=True, init=False)
class GovernanceAuthority:
    """Governance target identity.

    Production instances are deliberately not publicly constructible.  The public
    constructor exists only for the isolated controlled test harness and requires
    that mode to be stated explicitly.
    """

    authority_type: str
    publication_id: str
    publication_semantic_hash: str
    repository_semantic_hash: str
    upstream_phase03_attestation_sha256: str
    upstream_phase03_diagnostic_package_hash: str
    _issue_documents: Mapping[str, bytes]
    _production_source: _ProductionAuthoritySource | None

    def __init__(
        self,
        *,
        authority_type: str,
        publication_id: str,
        publication_semantic_hash: str,
        repository_semantic_hash: str,
        upstream_phase03_attestation_sha256: str,
        upstream_phase03_diagnostic_package_hash: str,
        issues: Mapping[str, Mapping[str, Any]],
    ) -> None:
        if authority_type != CONTROLLED_HARNESS_AUTHORITY_TYPE:
            raise GovernanceError(
                GovernanceErrorCode.AUTHORITY_MISMATCH,
                "production governance authority must be loaded from exact artifacts",
            )
        normalized = _normalize_authority_values(
            publication_id=publication_id,
            publication_semantic_hash=publication_semantic_hash,
            repository_semantic_hash=repository_semantic_hash,
            upstream_phase03_attestation_sha256=(
                upstream_phase03_attestation_sha256
            ),
            upstream_phase03_diagnostic_package_hash=(
                upstream_phase03_diagnostic_package_hash
            ),
            issues=issues,
        )
        object.__setattr__(self, "authority_type", authority_type)
        object.__setattr__(self, "publication_id", publication_id)
        object.__setattr__(
            self, "publication_semantic_hash", publication_semantic_hash
        )
        object.__setattr__(self, "repository_semantic_hash", repository_semantic_hash)
        object.__setattr__(
            self,
            "upstream_phase03_attestation_sha256",
            upstream_phase03_attestation_sha256,
        )
        object.__setattr__(
            self,
            "upstream_phase03_diagnostic_package_hash",
            upstream_phase03_diagnostic_package_hash,
        )
        object.__setattr__(self, "_issue_documents", MappingProxyType(normalized))
        object.__setattr__(self, "_production_source", None)

    @property
    def issues(self) -> Mapping[str, Mapping[str, Any]]:
        """Return a defensive projection of the immutable authority issues."""

        return MappingProxyType(
            {
                diagnostic_id: strict_json_bytes(document)
                for diagnostic_id, document in self._issue_documents.items()
            }
        )

    @property
    def binding(self) -> dict[str, str]:
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

    @property
    def upstream_phase03_issues_total(self) -> int:
        return len(self._issue_documents)

    def require_issue(
        self, diagnostic_id: str, diagnostic_basis_hash: str | None = None
    ) -> dict[str, Any]:
        document = self._issue_documents.get(diagnostic_id)
        if document is None:
            raise GovernanceError(GovernanceErrorCode.UNKNOWN_DIAGNOSTIC)
        issue = strict_json_bytes(document)
        if not isinstance(issue, dict):  # pragma: no cover - construction invariant
            raise GovernanceError(GovernanceErrorCode.AUTHORITY_MISMATCH)
        if (
            diagnostic_basis_hash is not None
            and issue.get("diagnostic_basis_hash") != diagnostic_basis_hash
        ):
            raise GovernanceError(GovernanceErrorCode.STALE_DIAGNOSTIC_BINDING)
        return issue

    def assert_same_current_authority(self, expected: Mapping[str, Any]) -> None:
        if any(expected.get(key) != value for key, value in self.binding.items()):
            raise GovernanceError(GovernanceErrorCode.STALE_DIAGNOSTIC_BINDING)


def _normalize_authority_values(
    *,
    publication_id: str,
    publication_semantic_hash: str,
    repository_semantic_hash: str,
    upstream_phase03_attestation_sha256: str,
    upstream_phase03_diagnostic_package_hash: str,
    issues: Mapping[str, Mapping[str, Any]],
) -> dict[str, bytes]:
    hashes = (
        publication_semantic_hash,
        repository_semantic_hash,
        upstream_phase03_attestation_sha256,
        upstream_phase03_diagnostic_package_hash,
    )
    if (
        not isinstance(publication_id, str)
        or not publication_id.endswith(publication_semantic_hash)
        or not all(_valid_hash(value) for value in hashes)
        or not isinstance(issues, Mapping)
    ):
        raise GovernanceError(GovernanceErrorCode.AUTHORITY_MISMATCH)
    normalized: dict[str, bytes] = {}
    for diagnostic_id, issue in issues.items():
        if (
            not isinstance(diagnostic_id, str)
            or not isinstance(issue, Mapping)
            or issue.get("diagnostic_id") != diagnostic_id
        ):
            raise GovernanceError(GovernanceErrorCode.AUTHORITY_MISMATCH)
        normalized[diagnostic_id] = canonical_json_bytes(dict(issue))
    return normalized


def _load_production_phase03_authority_impl(
    *,
    publication_package_directory: Path,
    publication_attestation_path: Path,
    phase01_artifact_directory: Path,
    phase02_artifact_directory: Path,
    phase03_artifact_directory: Path,
    expected_commit_sha: str,
    publication_scenario: str = "full-confirmation",
) -> dict[str, Any]:
    """Reconstruct and bind the sole production Phase 03 authority.

    No authority snapshot, diagnostic package, attestation mapping, or opaque
    ``GovernanceAuthority`` is accepted from the caller.  Every semantic value is
    reconstructed from the exact verified Stage08/Phase01/Phase02 artifacts and
    compared with the exact five-file Phase03 artifact.
    """

    values = (
        publication_package_directory,
        publication_attestation_path,
        phase01_artifact_directory,
        phase02_artifact_directory,
        phase03_artifact_directory,
    )
    for value in values:
        _reject_test_fixture(value)
    try:
        if not isinstance(expected_commit_sha, str) or _COMMIT.fullmatch(
            expected_commit_sha
        ) is None:
            raise ValueError("invalid expected commit SHA")

        publication_manifest_path = (
            Path(publication_package_directory) / "publication-manifest.json"
        )
        publication_attestation_file = Path(publication_attestation_path)
        phase01_attestation_path = (
            Path(phase01_artifact_directory) / "application-attestation.json"
        )
        publication_manifest_bytes = publication_manifest_path.read_bytes()
        publication_attestation_bytes = publication_attestation_file.read_bytes()
        phase01_attestation_bytes = phase01_attestation_path.read_bytes()
        phase02_root = Path(phase02_artifact_directory)
        phase02_attestation_path = (
            phase02_root / "application-phase02-attestation.json"
        )
        upstream_tree_digests_before = (
            _artifact_tree_digest(Path(publication_package_directory)),
            _artifact_tree_digest(publication_attestation_file.parent),
            _artifact_tree_digest(Path(phase01_artifact_directory)),
            _artifact_tree_digest(phase02_root),
        )
        phase02_bytes_before = phase02_attestation_path.read_bytes()
        verified_phase02 = verify_application_phase02_artifact(phase02_root)
        phase02_bytes_after = phase02_attestation_path.read_bytes()
        if phase02_bytes_before != phase02_bytes_after:
            raise ValueError("Phase02 attestation changed during verification")
        phase02_attestation = strict_json_bytes(phase02_bytes_after)
        if not isinstance(phase02_attestation, dict):
            raise TypeError("Phase02 attestation root is not an object")
        if (
            verified_phase02.get("status") != "APPLICATION_WORKBENCH_VERIFIED"
            or verified_phase02.get("commit_sha") != expected_commit_sha
            or phase02_attestation.get("commit_sha") != expected_commit_sha
        ):
            raise ValueError("Phase02 commit SHA binding mismatch")

        snapshot = load_verified_authority_snapshot(
            publication_package_directory=Path(publication_package_directory),
            publication_attestation_path=Path(publication_attestation_path),
            publication_scenario=publication_scenario,
            phase01_artifact_directory=Path(phase01_artifact_directory),
            phase02_artifact_directory=phase02_root,
        )
        stable_inputs = (
            (publication_manifest_path.read_bytes(), publication_manifest_bytes),
            (
                publication_attestation_file.read_bytes(),
                publication_attestation_bytes,
            ),
            (phase01_attestation_path.read_bytes(), phase01_attestation_bytes),
            (phase02_attestation_path.read_bytes(), phase02_bytes_after),
        )
        if any(current != frozen for current, frozen in stable_inputs):
            raise ValueError("upstream authority changed during reconstruction")
        upstream_tree_digests_after = (
            _artifact_tree_digest(Path(publication_package_directory)),
            _artifact_tree_digest(publication_attestation_file.parent),
            _artifact_tree_digest(Path(phase01_artifact_directory)),
            _artifact_tree_digest(phase02_root),
        )
        if upstream_tree_digests_after != upstream_tree_digests_before:
            raise ValueError("upstream artifact tree changed during reconstruction")
        package = reconstruct_diagnostics(snapshot).to_dict()
        package_hash = package["manifest"]["package_semantic_hash"]
        bindings = snapshot.authority_bindings
        if (
            hashlib.sha256(phase01_attestation_bytes).hexdigest()
            != bindings.phase01_attestation_hash
            or hashlib.sha256(phase02_bytes_after).hexdigest()
            != bindings.phase02_attestation_hash
        ):
            raise ValueError("upstream application physical lineage mismatch")

        phase03_root = Path(phase03_artifact_directory)
        phase03_tree_digest_before = _artifact_tree_digest(phase03_root)
        phase03_attestation_path = (
            phase03_root / "application-phase03-attestation.json"
        )
        attestation_bytes_before = phase03_attestation_path.read_bytes()
        verified_phase03 = verify_application_phase03_artifact(
            phase03_root,
            expected_commit_sha=expected_commit_sha,
        )
        attestation_bytes = phase03_attestation_path.read_bytes()
        if attestation_bytes_before != attestation_bytes:
            raise ValueError("Phase03 attestation changed during verification")
        phase03_attestation = strict_json_bytes(attestation_bytes)
        if not isinstance(phase03_attestation, dict):
            raise TypeError("Phase03 attestation root is not an object")
        attestation_sha256 = hashlib.sha256(attestation_bytes).hexdigest()

        coverage = package["coverage"]
        summary = package["summary"]
        expected_pairs = (
            (verified_phase03.get("status"), "APPLICATION_DIAGNOSTICS_VERIFIED"),
            (verified_phase03.get("commit_sha"), expected_commit_sha),
            (verified_phase03.get("diagnostic_package_hash"), package_hash),
            (verified_phase03.get("issues_total"), summary["issues_total"]),
            (phase03_attestation.get("status"), "APPLICATION_DIAGNOSTICS_VERIFIED"),
            (phase03_attestation.get("commit_sha"), expected_commit_sha),
            (phase03_attestation.get("publication_id"), bindings.publication_id),
            (
                phase03_attestation.get("publication_semantic_hash"),
                bindings.publication_semantic_hash,
            ),
            (
                phase03_attestation.get("phase01_attestation_hash"),
                bindings.phase01_attestation_hash,
            ),
            (
                phase03_attestation.get("phase02_attestation_hash"),
                bindings.phase02_attestation_hash,
            ),
            (
                phase03_attestation.get("query_registry_hash"),
                bindings.query_registry_hash,
            ),
            (
                phase03_attestation.get("repository_expected_hash"),
                bindings.repository_semantic_hash,
            ),
            (
                phase03_attestation.get("repository_before_hash"),
                bindings.repository_semantic_hash,
            ),
            (
                phase03_attestation.get("repository_after_hash"),
                bindings.repository_semantic_hash,
            ),
            (phase03_attestation.get("repository_unchanged"), True),
            (
                phase03_attestation.get("diagnostic_policy_hash"),
                bindings.diagnostic_policy_hash,
            ),
            (phase03_attestation.get("diagnostic_package_hash"), package_hash),
            (phase03_attestation.get("issues_total"), summary["issues_total"]),
            (
                phase03_attestation.get("issues_by_classification"),
                summary["issues_by_classification"],
            ),
            (
                phase03_attestation.get("requirements_evaluated"),
                coverage["requirements_evaluated"],
            ),
            (
                phase03_attestation.get("constraints_evaluated"),
                coverage["shacl_constraints_evaluated"],
            ),
        )
        if any(left != right for left, right in expected_pairs):
            raise ValueError("exact Phase03 authority lineage mismatch")
        if _artifact_tree_digest(phase03_root) != phase03_tree_digest_before:
            raise ValueError("Phase03 artifact tree changed during verification")

        issues = {
            issue["diagnostic_id"]: deepcopy(issue) for issue in package["issues"]
        }
        return {
            "publication_id": bindings.publication_id,
            "publication_semantic_hash": bindings.publication_semantic_hash,
            "repository_semantic_hash": bindings.repository_semantic_hash,
            "upstream_phase03_attestation_sha256": attestation_sha256,
            "upstream_phase03_diagnostic_package_hash": package_hash,
            "issues": issues,
        }
    except GovernanceError:
        raise
    except Exception as exc:
        raise GovernanceError(
            GovernanceErrorCode.AUTHORITY_MISMATCH,
            "exact production Phase03 authority reconstruction failed",
        ) from exc


def _construct_production_authority(
    values: Mapping[str, Any], source: _ProductionAuthoritySource
) -> GovernanceAuthority:
    """Materialize values only after the exact loader has reconstructed them."""

    normalized = _normalize_authority_values(**values)
    authority = object.__new__(GovernanceAuthority)
    object.__setattr__(authority, "authority_type", PRODUCTION_AUTHORITY_TYPE)
    for field in (
        "publication_id",
        "publication_semantic_hash",
        "repository_semantic_hash",
        "upstream_phase03_attestation_sha256",
        "upstream_phase03_diagnostic_package_hash",
    ):
        object.__setattr__(authority, field, values[field])
    object.__setattr__(authority, "_issue_documents", MappingProxyType(normalized))
    object.__setattr__(authority, "_production_source", source)
    return authority


def load_production_phase03_authority(
    *,
    publication_package_directory: Path,
    publication_attestation_path: Path,
    phase01_artifact_directory: Path,
    phase02_artifact_directory: Path,
    phase03_artifact_directory: Path,
    expected_commit_sha: str,
    publication_scenario: str = "full-confirmation",
) -> GovernanceAuthority:
    """Load production authority exclusively from independently verified files."""

    values = _load_production_phase03_authority_impl(
        publication_package_directory=publication_package_directory,
        publication_attestation_path=publication_attestation_path,
        phase01_artifact_directory=phase01_artifact_directory,
        phase02_artifact_directory=phase02_artifact_directory,
        phase03_artifact_directory=phase03_artifact_directory,
        expected_commit_sha=expected_commit_sha,
        publication_scenario=publication_scenario,
    )
    source = _ProductionAuthoritySource(
        publication_package_directory=Path(publication_package_directory).absolute(),
        publication_attestation_path=Path(publication_attestation_path).absolute(),
        phase01_artifact_directory=Path(phase01_artifact_directory).absolute(),
        phase02_artifact_directory=Path(phase02_artifact_directory).absolute(),
        phase03_artifact_directory=Path(phase03_artifact_directory).absolute(),
        expected_commit_sha=expected_commit_sha,
        publication_scenario=publication_scenario,
    )
    return _construct_production_authority(values, source)


def _authority_semantic_values(authority: GovernanceAuthority) -> dict[str, Any]:
    return {
        "publication_id": authority.publication_id,
        "publication_semantic_hash": authority.publication_semantic_hash,
        "repository_semantic_hash": authority.repository_semantic_hash,
        "upstream_phase03_attestation_sha256": (
            authority.upstream_phase03_attestation_sha256
        ),
        "upstream_phase03_diagnostic_package_hash": (
            authority.upstream_phase03_diagnostic_package_hash
        ),
        "issues": dict(authority.issues),
    }


def _require_verified_production_authority(authority: object) -> GovernanceAuthority:
    _reject_test_fixture(authority)
    if (
        isinstance(authority, GovernanceAuthority)
        and authority.authority_type == CONTROLLED_HARNESS_AUTHORITY_TYPE
    ):
        raise GovernanceError(
            GovernanceErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY
        )
    if type(authority) is not GovernanceAuthority:
        raise GovernanceError(
            GovernanceErrorCode.AUTHORITY_MISMATCH,
            "production governance authority must be loaded from exact artifacts",
        )
    try:
        if authority.authority_type != PRODUCTION_AUTHORITY_TYPE:
            raise ValueError("not a production authority")
        source = authority._production_source
        if not isinstance(source, _ProductionAuthoritySource):
            raise TypeError("missing exact artifact source")
        reconstructed = _load_production_phase03_authority_impl(
            **source.loader_arguments()
        )
        if canonical_json_bytes(reconstructed) != canonical_json_bytes(
            _authority_semantic_values(authority)
        ):
            raise ValueError("authority differs from exact artifact reconstruction")
    except GovernanceError:
        raise
    except Exception as exc:
        raise GovernanceError(
            GovernanceErrorCode.AUTHORITY_MISMATCH,
            "production governance authority differs from exact artifacts",
        ) from exc
    # Never continue with the caller-owned object.  Python mappings and private
    # attributes are reflectable and may expose inconsistent ``items``/``get``
    # behavior.  The only authority returned across this gate is rebuilt from
    # the just-verified exact artifact values.
    return _construct_production_authority(reconstructed, source)
