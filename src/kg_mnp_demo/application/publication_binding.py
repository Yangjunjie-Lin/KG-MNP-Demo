"""Bind the application runtime to one verified publication and repository lineage."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .._path_security import UnsafePathError, closed_regular_files, safe_artifact_path, validated_directory
from ..graphdb.contracts import validate_graphdb_contract
from ..publication.contracts import (
    validate_publication_attestation_evidence,
    validate_publication_contract,
)
from ..publication.package_validator import (
    validate_end_to_end_publication_package_against_authorities,
)
from .errors import ApplicationError, ErrorCode
from .policy import GraphRole, graph_role_for_iri


PUBLICATION_SCENARIOS = frozenset(
    {
        "full-confirmation",
        "modified-confirmation",
        "rejection",
        "issue-resolution",
    }
)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
        result[key] = value
    return result


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
    except Exception as exc:
        raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH) from exc
    if not isinstance(value, dict):
        raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
    return value


@dataclass(frozen=True, init=False)
class PublicationBinding:
    package_directory: Path
    attestation_directory: Path
    manifest: Mapping[str, Any]
    attestation: Mapping[str, Any]
    graphdb_manifest: Mapping[str, Any]
    compilation_manifest: Mapping[str, Any]
    graphs: Mapping[GraphRole, tuple[str, ...]]
    publication_scenario: str
    _authority_reconstruction: Mapping[str, Any]

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("PublicationBinding must be created by verify()")

    @property
    def publication_id(self) -> str:
        return str(self.manifest["publication_id"])

    @property
    def publication_semantic_hash(self) -> str:
        return str(self.manifest["publication_semantic_hash"])

    @property
    def repository_id(self) -> str:
        return str(self.graphdb_manifest["repository_id"])

    @property
    def compilation_id(self) -> str:
        return str(self.manifest["compilation_id"])

    @property
    def graphdb_semantic_hash(self) -> str:
        return str(self.graphdb_manifest["assembled_dataset_semantic_hash"])

    @property
    def publication_authority_reconstruction(self) -> dict[str, Any]:
        """Return the immutable facts established by the Stage 08 validator."""

        return dict(self._authority_reconstruction)

    def graph_iris(self, role: GraphRole) -> tuple[str, ...]:
        values = self.graphs.get(role, ())
        if not values:
            raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
        return values

    @classmethod
    def verify(
        cls,
        package_directory: Path,
        attestation_path: Path,
        *,
        publication_scenario: str | None = None,
        expected_repository_id: str | None = None,
    ) -> "PublicationBinding":
        try:
            package = validated_directory(Path(package_directory), label="publication package")
            attestation_file = Path(attestation_path).resolve(strict=True)
            if not attestation_file.is_file() or attestation_file.name != "publication-attestation.json":
                raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
            report = validated_directory(attestation_file.parent, label="publication attestation")
            manifest_path = safe_artifact_path(package, "publication-manifest.json", label="publication manifest")
        except (OSError, UnsafePathError) as exc:
            raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH) from exc
        if (
            not isinstance(publication_scenario, str)
            or publication_scenario not in PUBLICATION_SCENARIOS
        ):
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
        manifest = _json(manifest_path)
        attestation = _json(attestation_file)
        validate_publication_contract("end-to-end-publication-manifest", manifest)
        supporting = {
            name: _json(report / name)
            for name in (
                "publication-manifest.json",
                "visualization-manifest.json",
                "ontology-visualization-coverage.json",
                "representation-loss.json",
                "tbox-equivalence.json",
                "upstream-lock.json",
                "browser-smoke.json",
                "webvowl-runtime.json",
            )
        }
        if supporting["publication-manifest.json"] != manifest:
            raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
        try:
            validate_publication_attestation_evidence(
                attestation,
                publication_manifest=manifest,
                visualization_manifest=supporting["visualization-manifest.json"],
                coverage=supporting["ontology-visualization-coverage.json"],
                representation_loss=supporting["representation-loss.json"],
                tbox_equivalence=supporting["tbox-equivalence.json"],
                upstream_lock=supporting["upstream-lock.json"],
                browser_smoke=supporting["browser-smoke.json"],
                webvowl_runtime=supporting["webvowl-runtime.json"],
            )
        except Exception as exc:
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED) from exc
        if attestation.get("status") != "PUBLICATION_VERIFIED":
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
        expected_paths = {"publication-manifest.json"}
        for record in manifest["artifact_manifest"]:
            relative = str(record["relative_path"])
            expected_paths.add(relative)
            try:
                artifact = safe_artifact_path(package, relative, label="publication artifact")
                actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
            except (OSError, UnsafePathError) as exc:
                raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH) from exc
            if actual_hash != record["byte_sha256"]:
                raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
        try:
            actual_paths = set(closed_regular_files(package, label="publication package"))
        except UnsafePathError as exc:
            raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH) from exc
        if actual_paths != expected_paths:
            raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
        graphdb_manifest = _json(package / "source/graphdb-import-manifest.json")
        compilation_manifest = _json(package / "source/compilation-manifest.json")
        try:
            validate_graphdb_contract("graphdb-import-manifest", graphdb_manifest)
        except Exception as exc:
            raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH) from exc
        lineage_pairs = (
            (manifest.get("graphdb_publication_id"), graphdb_manifest.get("publication_id")),
            (manifest.get("graphdb_publication_semantic_hash"), graphdb_manifest.get("publication_semantic_hash")),
            (manifest.get("compilation_id"), graphdb_manifest.get("source_compilation_id")),
            (manifest.get("compilation_id"), compilation_manifest.get("compilation_id")),
        )
        if any(left != right for left, right in lineage_pairs):
            raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
        if expected_repository_id and graphdb_manifest.get("repository_id") != expected_repository_id:
            raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
        try:
            reconstruction = validate_end_to_end_publication_package_against_authorities(
                package,
                scenario=publication_scenario,
            )
        except Exception as exc:
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED) from exc
        required_reconstruction = {
            "valid": True,
            "deterministic_reconstruction_match": True,
            "publication_status": "READY_FOR_PRESENTATION",
            "publication_id": manifest.get("publication_id"),
        }
        if any(
            reconstruction.get(key) != expected
            for key, expected in required_reconstruction.items()
        ):
            raise ApplicationError(ErrorCode.FOUNDATION_NOT_VERIFIED)
        graphs: dict[GraphRole, list[str]] = {role: [] for role in GraphRole}
        for iri in graphdb_manifest.get("named_graphs", []):
            role = graph_role_for_iri(str(iri))
            if role is None:
                raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
            graphs[role].append(str(iri))
        if any(not graphs[role] for role in GraphRole):
            raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
        if any(len(graphs[role]) != 1 for role in GraphRole if role is not GraphRole.TBOX):
            raise ApplicationError(ErrorCode.PUBLICATION_MISMATCH)
        binding = object.__new__(cls)
        values = {
            "package_directory": package,
            "attestation_directory": report,
            "manifest": MappingProxyType(dict(manifest)),
            "attestation": MappingProxyType(dict(attestation)),
            "graphdb_manifest": MappingProxyType(dict(graphdb_manifest)),
            "compilation_manifest": MappingProxyType(dict(compilation_manifest)),
            "graphs": MappingProxyType(
                {
                    role: tuple(sorted(graph_values))
                    for role, graph_values in graphs.items()
                }
            ),
            "publication_scenario": publication_scenario,
            "_authority_reconstruction": MappingProxyType(
                {
                    "status": "PASS",
                    "scenario": publication_scenario,
                    "publication_id": reconstruction["publication_id"],
                    "deterministic_reconstruction_match": reconstruction[
                        "deterministic_reconstruction_match"
                    ],
                }
            ),
        }
        for name, value in values.items():
            object.__setattr__(binding, name, value)
        return binding
