"""Exact Stage08--Phase04 authority binding for production Phase 05."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kg_mnp_demo.governance.artifact_verifier import (
    verify_application_phase04_artifact,
)
from kg_mnp_demo.governance.authority_binding import (
    load_production_phase03_authority,
)
from kg_mnp_demo.governance.contracts import strict_json_file
from kg_mnp_demo.governance.validator import (
    validate_governance_workspace_against_authorities,
)
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from .errors import AmendmentError, AmendmentErrorCode

HASH = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
PRODUCTION_AUTHORITY_TYPE = "PRODUCTION_EXACT_PHASE04"
CONTROLLED_AUTHORITY_TYPE = "CONTROLLED_TEST_HARNESS"


def _reject_fixture(value: Any) -> None:
    if isinstance(value, Mapping) or hasattr(value, "fixture_type"):
        getter = (
            value.get
            if isinstance(value, Mapping)
            else lambda key: getattr(value, key, None)
        )
        marker = getter("fixture_type") or getter("status")
        if (
            getter("test_only") is True
            or getter("production_authority") is False
            or marker
            in {
                "PHASE04_CONTROLLED_DIAGNOSTIC_FIXTURE",
                "CONTROLLED_DIAGNOSTIC_FIXTURE",
            }
        ):
            raise AmendmentError(
                AmendmentErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY
            )
    if isinstance(value, (str, Path)) and "test-fixture" in str(value).casefold():
        raise AmendmentError(
            AmendmentErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY
        )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _publication_attestation(stage08: Path) -> Path:
    candidates = (
        stage08 / "publication-attestation.json",
        stage08.parent / "publication-attestation.json",
        stage08 / "attestation.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise AmendmentError(
        AmendmentErrorCode.AUTHORITY_MISMATCH,
        "Stage08 publication-attestation.json is required",
    )


@dataclass(frozen=True, slots=True)
class _ProductionPhase05Source:
    """Repeatable exact-artifact source; never an in-process credential."""

    stage08_artifact: Path
    publication_attestation: Path
    phase01_artifact: Path
    phase02_artifact: Path
    phase03_artifact: Path
    phase04_artifact: Path
    expected_commit_sha: str
    publication_scenario: str


@dataclass(frozen=True, slots=True, init=False)
class ProductionPhase05Authority:
    """Non-publicly-constructible projection of verified production requests."""

    commit_sha: str
    stage08_artifact_hash: str
    phase01_artifact_hash: str
    phase02_artifact_hash: str
    phase03_artifact_hash: str
    phase04_artifact_hash: str
    phase04_workspace_hash: str
    phase04_attestation_sha256: str
    publication_id: str
    publication_semantic_hash: str
    repository_semantic_hash: str
    approved_amendment_requests: tuple[dict[str, Any], ...]
    authority_type: str = PRODUCTION_AUTHORITY_TYPE
    _production_source: _ProductionPhase05Source | None = None

    @property
    def production_pending_amendments(self) -> int:
        return len(self.approved_amendment_requests)

    @property
    def binding(self) -> dict[str, Any]:
        return {
            "authority_type": self.authority_type,
            "commit_sha": self.commit_sha,
            "publication_id": self.publication_id,
            "publication_semantic_hash": self.publication_semantic_hash,
            "repository_semantic_hash": self.repository_semantic_hash,
            "phase04_attestation_sha256": self.phase04_attestation_sha256,
            "phase04_workspace_hash": self.phase04_workspace_hash,
            "stage08_artifact_hash": self.stage08_artifact_hash,
            "phase01_artifact_hash": self.phase01_artifact_hash,
            "phase02_artifact_hash": self.phase02_artifact_hash,
            "phase03_artifact_hash": self.phase03_artifact_hash,
            "phase04_artifact_hash": self.phase04_artifact_hash,
        }

    def require_request(self, amendment_request_id: str) -> dict[str, Any]:
        for request in self.approved_amendment_requests:
            if request.get("amendment_request_id") == amendment_request_id:
                return dict(request)
        raise AmendmentError(
            AmendmentErrorCode.UNAPPROVED_AMENDMENT,
            f"request is not present in exact production Phase04 authority: {amendment_request_id}",
        )


def _load_production_phase05_values(
    source: _ProductionPhase05Source,
) -> dict[str, Any]:
    """Reconstruct values from the exact physical source without trusting an object."""

    for value in (
        source.stage08_artifact,
        source.phase01_artifact,
        source.phase02_artifact,
        source.phase03_artifact,
        source.phase04_artifact,
    ):
        _reject_fixture(value)
    if not COMMIT.fullmatch(str(source.expected_commit_sha)):
        raise AmendmentError(
            AmendmentErrorCode.AUTHORITY_MISMATCH, "invalid commit SHA"
        )
    stage08 = source.stage08_artifact.resolve(strict=True)
    if not stage08.is_dir():
        raise AmendmentError(
            AmendmentErrorCode.AUTHORITY_MISMATCH,
            "Stage08 artifact must be a directory",
        )
    attestation_path = source.publication_attestation.resolve(strict=True)
    try:
        phase03 = load_production_phase03_authority(
            publication_package_directory=stage08,
            publication_attestation_path=attestation_path,
            phase01_artifact_directory=source.phase01_artifact,
            phase02_artifact_directory=source.phase02_artifact,
            phase03_artifact_directory=source.phase03_artifact,
            expected_commit_sha=source.expected_commit_sha,
            publication_scenario=source.publication_scenario,
        )
        phase04_result = verify_application_phase04_artifact(
            source.phase04_artifact,
            publication_package_directory=stage08,
            publication_attestation_path=attestation_path,
            publication_scenario=source.publication_scenario,
            phase01_artifact_directory=source.phase01_artifact,
            phase02_artifact_directory=source.phase02_artifact,
            phase03_artifact_directory=source.phase03_artifact,
            expected_commit_sha=source.expected_commit_sha,
        )
        phase04_root = source.phase04_artifact.resolve(strict=True)
        summary = strict_json_file(phase04_root / "governance-summary.json")
        workspace = summary["production_workspace"]
        reconstructed = validate_governance_workspace_against_authorities(
            workspace,
            phase03,
            expected_workspace_hash=phase04_result["production_workspace_hash"],
        )
    except AmendmentError:
        raise
    except Exception as exc:
        raise AmendmentError(
            AmendmentErrorCode.AUTHORITY_MISMATCH,
            "exact Stage08--Phase04 production authority reconstruction failed",
        ) from exc

    requests: list[dict[str, Any]] = []
    for request in reconstructed["approved_amendment_requests"]:
        if request.get("authority_type") != "PRODUCTION_EXACT_PHASE03":
            raise AmendmentError(
                AmendmentErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY,
                "controlled amendment request cannot enter production authority",
            )
        if str(request.get("amendment_request_id", "")).startswith(
            "urn:kg-mnp:test-fixture:"
        ):
            raise AmendmentError(
                AmendmentErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_AUTHORITY
            )
        requests.append(dict(request))
    phase04_attestation_bytes = (
        phase04_root / "application-phase04-attestation.json"
    ).read_bytes()
    return {
        "commit_sha": source.expected_commit_sha,
        "stage08_artifact_hash": semantic_hash(
            {"tree_sha256": _sha(stage08 / "publication-manifest.json")}
        ),
        "phase01_artifact_hash": semantic_hash(
            {
                "tree_sha256": _sha(
                    source.phase01_artifact / "application-attestation.json"
                )
            }
        ),
        "phase02_artifact_hash": semantic_hash(
            {
                "tree_sha256": _sha(
                    source.phase02_artifact / "application-phase02-attestation.json"
                )
            }
        ),
        "phase03_artifact_hash": semantic_hash(
            {
                "tree_sha256": _sha(
                    source.phase03_artifact / "application-phase03-attestation.json"
                )
            }
        ),
        "phase04_artifact_hash": semantic_hash(
            {"tree_sha256": _sha(phase04_root / "governance-summary.json")}
        ),
        "phase04_workspace_hash": reconstructed["workspace_hash"],
        "phase04_attestation_sha256": hashlib.sha256(
            phase04_attestation_bytes
        ).hexdigest(),
        "publication_id": phase03.publication_id,
        "publication_semantic_hash": phase03.publication_semantic_hash,
        "repository_semantic_hash": phase03.repository_semantic_hash,
        "approved_amendment_requests": requests,
    }


def _construct_production_authority(
    values: Mapping[str, Any], source: _ProductionPhase05Source
) -> ProductionPhase05Authority:
    authority = object.__new__(ProductionPhase05Authority)
    for field in (
        "commit_sha",
        "stage08_artifact_hash",
        "phase01_artifact_hash",
        "phase02_artifact_hash",
        "phase03_artifact_hash",
        "phase04_artifact_hash",
        "phase04_workspace_hash",
        "phase04_attestation_sha256",
        "publication_id",
        "publication_semantic_hash",
        "repository_semantic_hash",
    ):
        object.__setattr__(authority, field, values[field])
    object.__setattr__(
        authority,
        "approved_amendment_requests",
        tuple(deepcopy(values["approved_amendment_requests"])),
    )
    object.__setattr__(authority, "authority_type", PRODUCTION_AUTHORITY_TYPE)
    object.__setattr__(authority, "_production_source", source)
    return authority


def load_production_phase05_authority(
    *,
    stage08_artifact: Path,
    phase01_artifact: Path,
    phase02_artifact: Path,
    phase03_artifact: Path,
    phase04_artifact: Path,
    expected_commit_sha: str,
    publication_scenario: str = "full-confirmation",
    publication_attestation: Path | None = None,
) -> ProductionPhase05Authority:
    """Reconstruct production authority solely from exact physical artifacts.

    No request, workspace, or governance object is accepted from the caller.
    """

    for value in (
        stage08_artifact,
        phase01_artifact,
        phase02_artifact,
        phase03_artifact,
        phase04_artifact,
    ):
        _reject_fixture(value)
    stage08 = Path(stage08_artifact).absolute()
    attestation = Path(
        publication_attestation or _publication_attestation(stage08)
    ).absolute()
    source = _ProductionPhase05Source(
        stage08_artifact=stage08,
        publication_attestation=attestation,
        phase01_artifact=Path(phase01_artifact).absolute(),
        phase02_artifact=Path(phase02_artifact).absolute(),
        phase03_artifact=Path(phase03_artifact).absolute(),
        phase04_artifact=Path(phase04_artifact).absolute(),
        expected_commit_sha=str(expected_commit_sha),
        publication_scenario=publication_scenario,
    )
    return _construct_production_authority(
        _load_production_phase05_values(source), source
    )


def require_production_authority(authority: object) -> ProductionPhase05Authority:
    _reject_fixture(authority)
    if type(authority) is not ProductionPhase05Authority:
        raise AmendmentError(
            AmendmentErrorCode.AUTHORITY_MISMATCH,
            "Phase05 production authority must be reconstructed from exact artifacts",
        )
    try:
        if authority.authority_type != PRODUCTION_AUTHORITY_TYPE:
            raise ValueError("not a production Phase05 authority")
        source = authority._production_source
        if not isinstance(source, _ProductionPhase05Source):
            raise TypeError("missing exact artifact source")
        reconstructed = _load_production_phase05_values(source)
        observed = {
            **authority.binding,
            "approved_amendment_requests": list(authority.approved_amendment_requests),
        }
        expected = {key: reconstructed[key] for key in observed}
        if canonical_json_bytes(observed) != canonical_json_bytes(expected):
            raise ValueError("authority differs from exact artifact reconstruction")
    except Exception as exc:
        raise AmendmentError(
            AmendmentErrorCode.AUTHORITY_MISMATCH,
            "Phase05 production authority differs from exact artifacts",
        ) from exc
    return _construct_production_authority(reconstructed, source)


def authority_semantic_hash(authority: ProductionPhase05Authority) -> str:
    verified = require_production_authority(authority)
    return semantic_hash(
        verified.binding
        | {"approved_amendment_requests": list(verified.approved_amendment_requests)}
    )
