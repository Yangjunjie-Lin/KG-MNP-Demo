"""Exact Stage08--Phase05 authority binding for Phase 06 activation.

Production authority is reconstructed from physical artifacts every time it
crosses the activation boundary.  Neither a caller-created authority object nor
the Phase05 controlled republication fixture is an admissible trust root.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kg_mnp_demo._path_security import (
    UnsafePathError,
    closed_regular_files,
    safe_artifact_path,
    validated_directory,
)
from kg_mnp_demo.amendment.artifact_verifier import (
    verify_application_phase05_artifact,
)
from kg_mnp_demo.amendment.authority_binding import (
    load_production_phase05_authority,
)
from kg_mnp_demo.application.publication_binding import PublicationBinding
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from .errors import ActivationError, ActivationErrorCode

HASH = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
PRODUCTION_AUTHORITY_TYPE = "PRODUCTION_EXACT_PHASE05"
CONTROLLED_AUTHORITY_TYPE = "CONTROLLED_PHASE06_TEST_HARNESS"
BASE_LINEAGE_SOURCE_TYPE = "BOOTSTRAP_CURRENT_REFERENCE"
CONTROLLED_BASE_LINEAGE_SOURCE_TYPE = "CONTROLLED_PHASE06_BOOTSTRAP"
CONTROLLED_CANDIDATE_LINEAGE_SOURCE_TYPE = "CONTROLLED_PHASE05_VERIFIED_PUBLICATION"


def _raw_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    folded: set[str] = set()
    for key, child in pairs:
        marker = key.casefold()
        if marker in folded:
            raise ValueError(f"duplicate JSON key: {key}")
        folded.add(marker)
        value[key] = child
    return value


def _strict_json_bytes(raw: bytes) -> dict[str, Any]:
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=lambda constant: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON number: {constant}")
        ),
    )
    if not isinstance(value, dict):
        raise TypeError("JSON root must be an object")
    return value


def _safe_file(path: Path, *, label: str) -> Path:
    supplied = Path(path)
    parent = validated_directory(supplied.parent, label=f"{label} directory")
    return safe_artifact_path(parent, supplied.name, label=label)


def _tree_snapshot(path: Path, *, label: str) -> tuple[Path, str]:
    """Hash the complete safe regular-file tree in canonical path order."""

    root = validated_directory(Path(path), label=label)
    files = closed_regular_files(root, label=label)
    records: list[dict[str, str]] = []
    for relative, file_path in sorted(files.items()):
        raw = file_path.read_bytes()
        records.append({"relative_path": relative, "byte_sha256": _raw_sha256(raw)})
    return root, _raw_sha256(canonical_json_bytes(records))


@dataclass(frozen=True, slots=True, init=False)
class VerifiedPublicationTarget(Mapping[str, str]):
    """Immutable deployment target reconstructed from verified physical files."""

    publication_id: str
    publication_semantic_hash: str
    repository_id: str
    repository_semantic_hash: str
    publication_attestation_sha256: str
    lineage_source_type: str
    lineage_source_attestation_sha256: str
    test_only: bool
    production_authority: bool
    _package_directory: Path
    _attestation_path: Path
    _publication_tree_sha256: str
    _publication_scenario: str
    _controlled_fixture_hash: str | None

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("VerifiedPublicationTarget is reconstructed from files")

    @property
    def descriptor(self) -> dict[str, str]:
        return {
            "publication_id": self.publication_id,
            "publication_semantic_hash": self.publication_semantic_hash,
            "repository_id": self.repository_id,
            "repository_semantic_hash": self.repository_semantic_hash,
            "publication_attestation_sha256": self.publication_attestation_sha256,
            "lineage_source_type": self.lineage_source_type,
            "lineage_source_attestation_sha256": (
                self.lineage_source_attestation_sha256
            ),
        }

    def to_dict(self) -> dict[str, str]:
        return self.descriptor

    def __getitem__(self, key: str) -> str:
        return self.descriptor[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.descriptor)

    def __len__(self) -> int:
        return len(self.descriptor)

    @property
    def package_directory(self) -> Path:
        return self._package_directory

    @property
    def attestation_path(self) -> Path:
        return self._attestation_path

    @property
    def publication_tree_sha256(self) -> str:
        return self._publication_tree_sha256

    @property
    def publication_scenario(self) -> str:
        return self._publication_scenario

    @property
    def controlled_fixture_hash(self) -> str | None:
        return self._controlled_fixture_hash


def _new_target(
    *,
    publication_id: str,
    publication_semantic_hash: str,
    repository_id: str,
    repository_semantic_hash: str,
    publication_attestation_sha256: str,
    lineage_source_type: str,
    lineage_source_attestation_sha256: str,
    package_directory: Path,
    attestation_path: Path,
    publication_tree_sha256: str,
    publication_scenario: str,
    test_only: bool,
    production_authority: bool,
    controlled_fixture_hash: str | None = None,
) -> VerifiedPublicationTarget:
    hashes = (
        publication_semantic_hash,
        repository_semantic_hash,
        publication_attestation_sha256,
        lineage_source_attestation_sha256,
        publication_tree_sha256,
    )
    if (
        not isinstance(publication_id, str)
        or not publication_id.endswith(publication_semantic_hash)
        or not isinstance(repository_id, str)
        or not repository_id
        or not isinstance(lineage_source_type, str)
        or not lineage_source_type
        or not isinstance(publication_scenario, str)
        or not publication_scenario
        or type(test_only) is not bool
        or type(production_authority) is not bool
        or test_only == production_authority
        or not all(isinstance(value, str) and HASH.fullmatch(value) for value in hashes)
        or (
            controlled_fixture_hash is not None
            and not HASH.fullmatch(controlled_fixture_hash)
        )
    ):
        raise ActivationError(ActivationErrorCode.AUTHORITY_MISMATCH)
    target = object.__new__(VerifiedPublicationTarget)
    values = {
        "publication_id": publication_id,
        "publication_semantic_hash": publication_semantic_hash,
        "repository_id": repository_id,
        "repository_semantic_hash": repository_semantic_hash,
        "publication_attestation_sha256": publication_attestation_sha256,
        "lineage_source_type": lineage_source_type,
        "lineage_source_attestation_sha256": lineage_source_attestation_sha256,
        "test_only": test_only,
        "production_authority": production_authority,
        "_package_directory": package_directory,
        "_attestation_path": attestation_path,
        "_publication_tree_sha256": publication_tree_sha256,
        "_publication_scenario": publication_scenario,
        "_controlled_fixture_hash": controlled_fixture_hash,
    }
    for name, value in values.items():
        object.__setattr__(target, name, value)
    return target


@dataclass(frozen=True, slots=True)
class _ProductionPhase06Source:
    publication_package_directory: Path
    publication_attestation_path: Path
    phase01_artifact_directory: Path
    phase02_artifact_directory: Path
    phase03_artifact_directory: Path
    phase04_artifact_directory: Path
    phase05_artifact_directory: Path
    expected_commit_sha: str
    publication_scenario: str

    def loader_arguments(self) -> dict[str, Any]:
        return {
            "publication_package_directory": self.publication_package_directory,
            "publication_attestation_path": self.publication_attestation_path,
            "phase01_artifact_directory": self.phase01_artifact_directory,
            "phase02_artifact_directory": self.phase02_artifact_directory,
            "phase03_artifact_directory": self.phase03_artifact_directory,
            "phase04_artifact_directory": self.phase04_artifact_directory,
            "phase05_artifact_directory": self.phase05_artifact_directory,
            "expected_commit_sha": self.expected_commit_sha,
            "publication_scenario": self.publication_scenario,
        }


@dataclass(frozen=True, slots=True, init=False)
class ProductionPhase06Authority:
    """Production activation authority, constructible only from exact artifacts."""

    commit_sha: str
    base_publication: VerifiedPublicationTarget
    activation_candidates: tuple[VerifiedPublicationTarget, ...]
    stage08_artifact_tree_sha256: str
    publication_attestation_tree_sha256: str
    phase01_artifact_tree_sha256: str
    phase02_artifact_tree_sha256: str
    phase03_artifact_tree_sha256: str
    phase04_artifact_tree_sha256: str
    phase05_artifact_tree_sha256: str
    phase05_attestation_sha256: str
    authority_type: str
    test_only: bool
    production_authority: bool
    _production_source: _ProductionPhase06Source | None

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError(
            "ProductionPhase06Authority must be loaded from exact artifacts"
        )

    @property
    def base_target(self) -> VerifiedPublicationTarget:
        return self.base_publication

    @property
    def production_activation_candidate_count(self) -> int:
        return len(self.activation_candidates)

    @property
    def binding(self) -> dict[str, Any]:
        return {
            "authority_type": self.authority_type,
            "commit_sha": self.commit_sha,
            "stage08_artifact_tree_sha256": self.stage08_artifact_tree_sha256,
            "publication_attestation_tree_sha256": (
                self.publication_attestation_tree_sha256
            ),
            "phase01_artifact_tree_sha256": self.phase01_artifact_tree_sha256,
            "phase02_artifact_tree_sha256": self.phase02_artifact_tree_sha256,
            "phase03_artifact_tree_sha256": self.phase03_artifact_tree_sha256,
            "phase04_artifact_tree_sha256": self.phase04_artifact_tree_sha256,
            "phase05_artifact_tree_sha256": self.phase05_artifact_tree_sha256,
            "phase05_attestation_sha256": self.phase05_attestation_sha256,
            "base_publication": self.base_publication.descriptor,
            "production_activation_candidates": [
                target.descriptor for target in self.activation_candidates
            ],
            "test_only": False,
            "production_authority": True,
        }

    @property
    def authority_binding_hash(self) -> str:
        return semantic_hash(self.binding)

    @property
    def binding_hash(self) -> str:
        return self.authority_binding_hash

    def resolve_target(self, publication_id: str) -> VerifiedPublicationTarget:
        for target in (self.base_publication, *self.activation_candidates):
            if target.publication_id == publication_id:
                return target
        raise ActivationError(ActivationErrorCode.UNVERIFIED_ACTIVATION_TARGET)

    def target_binding_hash(self, publication_id: str) -> str:
        return semantic_hash(
            {
                "authority_binding_hash": self.authority_binding_hash,
                "target": self.resolve_target(publication_id).descriptor,
            }
        )


def _source_paths(
    source: _ProductionPhase06Source,
) -> tuple[tuple[str, Path], ...]:
    return (
        ("stage08_artifact_tree_sha256", source.publication_package_directory),
        ("phase01_artifact_tree_sha256", source.phase01_artifact_directory),
        ("phase02_artifact_tree_sha256", source.phase02_artifact_directory),
        ("phase03_artifact_tree_sha256", source.phase03_artifact_directory),
        ("phase04_artifact_tree_sha256", source.phase04_artifact_directory),
        ("phase05_artifact_tree_sha256", source.phase05_artifact_directory),
    )


def _source_tree_snapshots(
    source: _ProductionPhase06Source,
) -> tuple[dict[str, Path], dict[str, str]]:
    roots: dict[str, Path] = {}
    digests: dict[str, str] = {}
    for field, path in _source_paths(source):
        root, digest = _tree_snapshot(path, label=field)
        roots[field] = root
        digests[field] = digest
    attestation_file = _safe_file(
        source.publication_attestation_path,
        label="publication attestation",
    )
    report_root, report_digest = _tree_snapshot(
        attestation_file.parent,
        label="publication attestation tree",
    )
    roots["publication_attestation_path"] = attestation_file
    roots["publication_attestation_tree_sha256"] = report_root
    digests["publication_attestation_tree_sha256"] = report_digest
    return roots, digests


def _translate_upstream_exception(exc: Exception) -> ActivationError:
    if isinstance(exc, UnsafePathError):
        return ActivationError(ActivationErrorCode.PATH_REJECTED)
    code = str(getattr(exc, "code", ""))
    if "TEST_FIXTURE_NOT_ALLOWED" in code:
        return ActivationError(
            ActivationErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET
        )
    return ActivationError(
        ActivationErrorCode.AUTHORITY_MISMATCH,
        "exact Stage08--Phase05 production authority reconstruction failed",
    )


def _load_production_phase06_values(
    source: _ProductionPhase06Source,
) -> dict[str, Any]:
    if not COMMIT.fullmatch(source.expected_commit_sha):
        raise ActivationError(
            ActivationErrorCode.AUTHORITY_MISMATCH,
            "invalid expected commit SHA",
        )
    if (
        any("test-fixture" in str(path).casefold() for _, path in _source_paths(source))
        or "test-fixture" in str(source.publication_attestation_path).casefold()
    ):
        raise ActivationError(
            ActivationErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET
        )
    try:
        roots_before, trees_before = _source_tree_snapshots(source)
        phase05 = load_production_phase05_authority(
            stage08_artifact=roots_before["stage08_artifact_tree_sha256"],
            publication_attestation=roots_before["publication_attestation_path"],
            phase01_artifact=roots_before["phase01_artifact_tree_sha256"],
            phase02_artifact=roots_before["phase02_artifact_tree_sha256"],
            phase03_artifact=roots_before["phase03_artifact_tree_sha256"],
            phase04_artifact=roots_before["phase04_artifact_tree_sha256"],
            expected_commit_sha=source.expected_commit_sha,
            publication_scenario=source.publication_scenario,
        )
        phase05_verification = verify_application_phase05_artifact(
            roots_before["phase05_artifact_tree_sha256"],
            stage08_artifact=roots_before["stage08_artifact_tree_sha256"],
            publication_attestation=roots_before["publication_attestation_path"],
            phase01_artifact=roots_before["phase01_artifact_tree_sha256"],
            phase02_artifact=roots_before["phase02_artifact_tree_sha256"],
            phase03_artifact=roots_before["phase03_artifact_tree_sha256"],
            phase04_artifact=roots_before["phase04_artifact_tree_sha256"],
            expected_commit_sha=source.expected_commit_sha,
            publication_scenario=source.publication_scenario,
        )
        publication = PublicationBinding.verify(
            roots_before["stage08_artifact_tree_sha256"],
            roots_before["publication_attestation_path"],
            publication_scenario=source.publication_scenario,
        )
        phase05_attestation_path = safe_artifact_path(
            roots_before["phase05_artifact_tree_sha256"],
            "application-phase05-attestation.json",
            label="Phase05 attestation",
        )
        phase05_attestation_raw = phase05_attestation_path.read_bytes()
        phase05_attestation = _strict_json_bytes(phase05_attestation_raw)
        publication_attestation_raw = roots_before[
            "publication_attestation_path"
        ].read_bytes()

        expected_pairs = (
            (phase05.commit_sha, source.expected_commit_sha),
            (phase05_verification.get("commit_sha"), source.expected_commit_sha),
            (phase05_attestation.get("commit_sha"), source.expected_commit_sha),
            (
                phase05_verification.get("status"),
                "APPLICATION_AMENDMENT_REPUBLICATION_VERIFIED",
            ),
            (
                phase05_attestation.get("status"),
                "APPLICATION_AMENDMENT_REPUBLICATION_VERIFIED",
            ),
            (phase05.publication_id, publication.publication_id),
            (
                phase05.publication_semantic_hash,
                publication.publication_semantic_hash,
            ),
            (phase05.repository_semantic_hash, publication.graphdb_semantic_hash),
            (phase05.production_pending_amendments, 0),
            (phase05_verification.get("production_pending_amendments"), 0),
            (phase05_attestation.get("production_reentry_cycles"), 0),
            (phase05_attestation.get("production_new_publications"), 0),
        )
        if any(left != right for left, right in expected_pairs):
            raise ValueError("Stage08--Phase05 production lineage mismatch")
        for root_key, filename in (
            ("phase02_artifact_tree_sha256", "application-phase02-attestation.json"),
            ("phase03_artifact_tree_sha256", "application-phase03-attestation.json"),
            ("phase04_artifact_tree_sha256", "application-phase04-attestation.json"),
        ):
            upstream_attestation = _strict_json_bytes(
                safe_artifact_path(
                    roots_before[root_key],
                    filename,
                    label=f"{root_key} attestation",
                ).read_bytes()
            )
            if upstream_attestation.get("commit_sha") != source.expected_commit_sha:
                raise ValueError("upstream artifact commit SHA mismatch")
        roots_after, trees_after = _source_tree_snapshots(source)
        if trees_before != trees_after:
            raise ValueError("upstream artifact tree changed during reconstruction")
        if (
            roots_after["publication_attestation_path"].read_bytes()
            != publication_attestation_raw
            or safe_artifact_path(
                roots_after["phase05_artifact_tree_sha256"],
                "application-phase05-attestation.json",
                label="Phase05 attestation",
            ).read_bytes()
            != phase05_attestation_raw
        ):
            raise ValueError("upstream attestation changed during reconstruction")
    except ActivationError:
        raise
    except (OSError, UnsafePathError, TypeError, ValueError) as exc:
        raise _translate_upstream_exception(exc) from exc
    except Exception as exc:
        raise _translate_upstream_exception(exc) from exc

    publication_attestation_sha256 = _raw_sha256(publication_attestation_raw)
    base = _new_target(
        publication_id=publication.publication_id,
        publication_semantic_hash=publication.publication_semantic_hash,
        repository_id=publication.repository_id,
        repository_semantic_hash=publication.graphdb_semantic_hash,
        publication_attestation_sha256=publication_attestation_sha256,
        lineage_source_type=BASE_LINEAGE_SOURCE_TYPE,
        lineage_source_attestation_sha256=publication_attestation_sha256,
        package_directory=roots_after["stage08_artifact_tree_sha256"],
        attestation_path=roots_after["publication_attestation_path"],
        publication_tree_sha256=trees_after["stage08_artifact_tree_sha256"],
        publication_scenario=source.publication_scenario,
        test_only=False,
        production_authority=True,
    )
    return {
        "commit_sha": source.expected_commit_sha,
        "base_publication": base,
        "activation_candidates": (),
        **trees_after,
        "phase05_attestation_sha256": _raw_sha256(phase05_attestation_raw),
    }


def _construct_production_authority(
    values: Mapping[str, Any],
    source: _ProductionPhase06Source,
) -> ProductionPhase06Authority:
    authority = object.__new__(ProductionPhase06Authority)
    for field in (
        "commit_sha",
        "base_publication",
        "activation_candidates",
        "stage08_artifact_tree_sha256",
        "publication_attestation_tree_sha256",
        "phase01_artifact_tree_sha256",
        "phase02_artifact_tree_sha256",
        "phase03_artifact_tree_sha256",
        "phase04_artifact_tree_sha256",
        "phase05_artifact_tree_sha256",
        "phase05_attestation_sha256",
    ):
        object.__setattr__(authority, field, values[field])
    object.__setattr__(authority, "authority_type", PRODUCTION_AUTHORITY_TYPE)
    object.__setattr__(authority, "test_only", False)
    object.__setattr__(authority, "production_authority", True)
    object.__setattr__(authority, "_production_source", source)
    return authority


def load_production_phase06_authority(
    *,
    publication_package_directory: Path,
    publication_attestation_path: Path,
    phase01_artifact_directory: Path,
    phase02_artifact_directory: Path,
    phase03_artifact_directory: Path,
    phase04_artifact_directory: Path,
    phase05_artifact_directory: Path,
    expected_commit_sha: str,
    publication_scenario: str = "full-confirmation",
) -> ProductionPhase06Authority:
    """Reconstruct production Phase06 authority solely from physical artifacts."""

    source = _ProductionPhase06Source(
        publication_package_directory=Path(publication_package_directory).absolute(),
        publication_attestation_path=Path(publication_attestation_path).absolute(),
        phase01_artifact_directory=Path(phase01_artifact_directory).absolute(),
        phase02_artifact_directory=Path(phase02_artifact_directory).absolute(),
        phase03_artifact_directory=Path(phase03_artifact_directory).absolute(),
        phase04_artifact_directory=Path(phase04_artifact_directory).absolute(),
        phase05_artifact_directory=Path(phase05_artifact_directory).absolute(),
        expected_commit_sha=str(expected_commit_sha),
        publication_scenario=publication_scenario,
    )
    return _construct_production_authority(
        _load_production_phase06_values(source), source
    )


def require_production_phase06_authority(
    authority: object,
) -> ProductionPhase06Authority:
    """Reverify the exact source and never continue with a caller-owned object."""

    if isinstance(authority, ControlledPhase06Authority) or (
        getattr(authority, "test_only", False) is True
        or getattr(authority, "production_authority", None) is False
    ):
        raise ActivationError(
            ActivationErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET
        )
    if type(authority) is not ProductionPhase06Authority:
        raise ActivationError(
            ActivationErrorCode.AUTHORITY_MISMATCH,
            "Phase06 authority must be reconstructed from exact artifacts",
        )
    try:
        source = authority._production_source
        if not isinstance(source, _ProductionPhase06Source):
            raise TypeError("missing exact Phase06 source")
        reconstructed = _load_production_phase06_values(source)
        expected_binding = _construct_production_authority(
            reconstructed, source
        ).binding
        if canonical_json_bytes(authority.binding) != canonical_json_bytes(
            expected_binding
        ):
            raise ValueError("authority differs from physical reconstruction")
    except ActivationError:
        raise
    except Exception as exc:
        raise ActivationError(
            ActivationErrorCode.AUTHORITY_MISMATCH,
            "Phase06 authority differs from exact artifact reconstruction",
        ) from exc
    return _construct_production_authority(reconstructed, source)


# The shorter name mirrors the established Phase04/05 production gate.
require_production_authority = require_production_phase06_authority


@dataclass(frozen=True, slots=True, init=False)
class ControlledPhase06Authority:
    """Explicit TEST-ONLY authority for controlled P0/P1 activation exercises."""

    fixture_id: str
    controlled_fixture_hash: str
    base_publication: VerifiedPublicationTarget
    activation_candidates: tuple[VerifiedPublicationTarget, ...]
    authority_type: str
    test_only: bool
    production_authority: bool

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("ControlledPhase06Authority must be created by create()")

    @classmethod
    def create(
        cls,
        *,
        p0_package_directory: Path,
        p0_manifest: Mapping[str, Any],
        p0_attestation_path: Path,
        p1_package_directory: Path,
        p1_manifest: Mapping[str, Any],
        p1_attestation_path: Path,
    ) -> ControlledPhase06Authority:
        p0 = _controlled_target(
            package_directory=p0_package_directory,
            supplied_manifest=p0_manifest,
            attestation_path=p0_attestation_path,
            publication_role="P0",
        )
        p1 = _controlled_target(
            package_directory=p1_package_directory,
            supplied_manifest=p1_manifest,
            attestation_path=p1_attestation_path,
            publication_role="P1",
        )
        if (
            p0.publication_id == p1.publication_id
            or p0.repository_id == p1.repository_id
        ):
            raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
        if (
            p0.controlled_fixture_hash is None
            or p0.controlled_fixture_hash != p1.controlled_fixture_hash
        ):
            raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
        fixture_id = "urn:kg-mnp:test-fixture:phase06:authority:" + semantic_hash(
            {"p0": p0.descriptor, "p1": p1.descriptor}
        )
        authority = object.__new__(cls)
        object.__setattr__(authority, "fixture_id", fixture_id)
        object.__setattr__(
            authority, "controlled_fixture_hash", p0.controlled_fixture_hash
        )
        object.__setattr__(authority, "base_publication", p0)
        object.__setattr__(authority, "activation_candidates", (p1,))
        object.__setattr__(authority, "authority_type", CONTROLLED_AUTHORITY_TYPE)
        object.__setattr__(authority, "test_only", True)
        object.__setattr__(authority, "production_authority", False)
        return authority

    from_preverified_publications = create

    @property
    def base_target(self) -> VerifiedPublicationTarget:
        return self.base_publication

    @property
    def binding(self) -> dict[str, Any]:
        return {
            "authority_type": self.authority_type,
            "fixture_id": self.fixture_id,
            "controlled_fixture_hash": self.controlled_fixture_hash,
            "base_publication": self.base_publication.descriptor,
            "activation_candidates": [
                target.descriptor for target in self.activation_candidates
            ],
            "test_only": True,
            "production_authority": False,
        }

    @property
    def authority_binding_hash(self) -> str:
        return semantic_hash(self.binding)

    @property
    def binding_hash(self) -> str:
        return self.authority_binding_hash

    def resolve_target(self, publication_id: str) -> VerifiedPublicationTarget:
        for target in (self.base_publication, *self.activation_candidates):
            if target.publication_id == publication_id:
                return target
        raise ActivationError(ActivationErrorCode.UNVERIFIED_ACTIVATION_TARGET)

    def target_binding_hash(self, publication_id: str) -> str:
        return semantic_hash(
            {
                "authority_binding_hash": self.authority_binding_hash,
                "target": self.resolve_target(publication_id).descriptor,
            }
        )


def _controlled_target(
    *,
    package_directory: Path,
    supplied_manifest: Mapping[str, Any],
    attestation_path: Path,
    publication_role: str,
) -> VerifiedPublicationTarget:
    try:
        package, before = _tree_snapshot(
            package_directory,
            label="controlled publication package",
        )
        manifest_path = safe_artifact_path(
            package,
            "publication-manifest.json",
            label="controlled publication manifest",
        )
        graphdb_path = safe_artifact_path(
            package,
            "source/graphdb-import-manifest.json",
            label="controlled GraphDB manifest",
        )
        manifest = _strict_json_bytes(manifest_path.read_bytes())
        graphdb = _strict_json_bytes(graphdb_path.read_bytes())
        attestation_file = _safe_file(
            attestation_path,
            label="controlled publication attestation",
        )
        attestation_raw = attestation_file.read_bytes()
        attestation = _strict_json_bytes(attestation_raw)
        if canonical_json_bytes(dict(supplied_manifest)) != canonical_json_bytes(
            manifest
        ):
            raise ValueError("controlled manifest differs from package")
        if (
            set(attestation)
            != {
                "contract_version",
                "fixture_type",
                "test_only",
                "production_authority",
                "controlled_fixture_hash",
                "publication_role",
                "publication_id",
                "publication_semantic_hash",
                "repository_id",
                "repository_semantic_hash",
                "phase05_publication_status",
                "semantic_authority",
                "deployment_governance_only",
                "status",
            }
            or attestation.get("fixture_type")
            != "PHASE06_CONTROLLED_ACTIVATION_FIXTURE"
            or attestation.get("test_only") is not True
            or attestation.get("production_authority") is not False
            or attestation.get("publication_role") != publication_role
            or attestation.get("phase05_publication_status")
            != (
                "VERIFIED_IMMUTABLE_BASE_PUBLICATION"
                if publication_role == "P0"
                else "VERIFIED_NEW_PUBLICATION_NOT_ACTIVATED"
            )
            or attestation.get("semantic_authority") is not False
            or attestation.get("deployment_governance_only") is not True
            or attestation.get("status") != "CONTROLLED_PHASE05_PUBLICATION_VERIFIED"
        ):
            raise ValueError("controlled attestation lacks test-only markers")
        for field in ("publication_id", "publication_semantic_hash"):
            if field in attestation and attestation[field] != manifest.get(field):
                raise ValueError("controlled attestation publication mismatch")
        if attestation.get("repository_id") != graphdb.get(
            "repository_id"
        ) or attestation.get("repository_semantic_hash") != graphdb.get(
            "assembled_dataset_semantic_hash"
        ):
            raise ValueError("controlled attestation repository mismatch")
        _, after = _tree_snapshot(
            package,
            label="controlled publication package",
        )
        if before != after or attestation_file.read_bytes() != attestation_raw:
            raise ValueError("controlled publication changed during reconstruction")
        return _new_target(
            publication_id=str(manifest["publication_id"]),
            publication_semantic_hash=str(manifest["publication_semantic_hash"]),
            repository_id=str(graphdb["repository_id"]),
            repository_semantic_hash=str(graphdb["assembled_dataset_semantic_hash"]),
            publication_attestation_sha256=_raw_sha256(attestation_raw),
            lineage_source_type=(
                CONTROLLED_BASE_LINEAGE_SOURCE_TYPE
                if publication_role == "P0"
                else CONTROLLED_CANDIDATE_LINEAGE_SOURCE_TYPE
            ),
            lineage_source_attestation_sha256=_raw_sha256(attestation_raw),
            package_directory=package,
            attestation_path=attestation_file,
            publication_tree_sha256=after,
            publication_scenario="controlled-phase06",
            test_only=True,
            production_authority=False,
            controlled_fixture_hash=str(attestation["controlled_fixture_hash"]),
        )
    except ActivationError:
        raise
    except Exception as exc:
        raise ActivationError(
            ActivationErrorCode.INVALID_ACTIVATION_REQUEST,
            "controlled publication fixture is not closed",
        ) from exc
