"""Immutable publication-byte evidence used by the activation control plane."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from kg_mnp_demo._path_security import (
    UnsafePathError,
    closed_regular_files,
    safe_artifact_path,
    validated_directory,
)
from kg_mnp_demo.application.publication_binding import PublicationBinding
from kg_mnp_demo.graphdb.contracts import validate_graphdb_contract
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash
from kg_mnp_demo.publication.contracts import validate_publication_contract

from .contracts import strict_json_file
from .errors import ActivationError, ActivationErrorCode

CONTROLLED_ATTESTATION_FIELDS = {
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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def publication_tree_sha256(directory: Path) -> str:
    """Hash the complete safe regular-file tree, including names and bytes."""

    try:
        root = validated_directory(Path(directory), label="activation publication")
        files = closed_regular_files(root, label="activation publication")
        records = [
            {
                "relative_path": relative,
                "byte_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for relative, path in sorted(files.items())
        ]
    except (OSError, UnsafePathError) as exc:
        raise ActivationError(
            ActivationErrorCode.TARGET_PUBLICATION_UNAVAILABLE
        ) from exc
    return hashlib.sha256(canonical_json_bytes(records)).hexdigest()


def build_controlled_publication_attestation(
    *,
    publication_manifest: Mapping[str, Any],
    graphdb_manifest: Mapping[str, Any],
    controlled_fixture_hash: str,
    publication_role: str,
) -> dict[str, Any]:
    """Build explicit test-only Phase05 lineage evidence for controlled P0/P1."""

    if publication_role not in {"P0", "P1"}:
        raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
    status = (
        "VERIFIED_IMMUTABLE_BASE_PUBLICATION"
        if publication_role == "P0"
        else "VERIFIED_NEW_PUBLICATION_NOT_ACTIVATED"
    )
    return {
        "contract_version": "1.0",
        "fixture_type": "PHASE06_CONTROLLED_ACTIVATION_FIXTURE",
        "test_only": True,
        "production_authority": False,
        "controlled_fixture_hash": controlled_fixture_hash,
        "publication_role": publication_role,
        "publication_id": publication_manifest["publication_id"],
        "publication_semantic_hash": publication_manifest["publication_semantic_hash"],
        "repository_id": graphdb_manifest["repository_id"],
        "repository_semantic_hash": graphdb_manifest["assembled_dataset_semantic_hash"],
        "phase05_publication_status": status,
        "semantic_authority": False,
        "deployment_governance_only": True,
        "status": "CONTROLLED_PHASE05_PUBLICATION_VERIFIED",
    }


def controlled_attestation_sha256(attestation: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(attestation) + b"\n").hexdigest()


def _verify_package_bytes(
    package_directory: Path,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    try:
        root = validated_directory(package_directory, label="activation publication")
        manifest = strict_json_file(
            safe_artifact_path(
                root,
                "publication-manifest.json",
                label="publication manifest",
            )
        )
        validate_publication_contract("end-to-end-publication-manifest", manifest)
        expected = {"publication-manifest.json"}
        for record in manifest["artifact_manifest"]:
            relative = record["relative_path"]
            expected.add(relative)
            path = safe_artifact_path(root, relative, label="publication artifact")
            if hashlib.sha256(path.read_bytes()).hexdigest() != record["byte_sha256"]:
                raise ValueError("publication artifact byte hash mismatch")
        if set(closed_regular_files(root, label="activation publication")) != expected:
            raise ValueError("publication package closed file set mismatch")
        graphdb = strict_json_file(
            safe_artifact_path(
                root,
                "source/graphdb-import-manifest.json",
                label="GraphDB import manifest",
            )
        )
        validate_graphdb_contract("graphdb-import-manifest", graphdb)
    except (OSError, UnsafePathError) as exc:
        raise ActivationError(
            ActivationErrorCode.TARGET_PUBLICATION_UNAVAILABLE
        ) from exc
    except ActivationError:
        raise
    except Exception as exc:
        raise ActivationError(ActivationErrorCode.TARGET_PUBLICATION_TAMPERED) from exc
    return root, manifest, graphdb


def verify_controlled_publication(
    *,
    package_directory: Path,
    attestation_path: Path,
    expected_publication_tree_sha256: str,
    expected_publication_id: str,
    expected_publication_semantic_hash: str,
    expected_repository_id: str,
    expected_repository_semantic_hash: str,
    expected_attestation_sha256: str,
    expected_controlled_fixture_hash: str,
) -> dict[str, Any]:
    root, manifest, graphdb = _verify_package_bytes(package_directory)
    try:
        supplied_attestation = Path(attestation_path)
        if supplied_attestation.is_symlink():
            raise ValueError("controlled attestation is a symlink")
        attestation_file = supplied_attestation.resolve(strict=True)
        if not attestation_file.is_file():
            raise FileNotFoundError("controlled attestation is unavailable")
        raw = attestation_file.read_bytes()
        attestation = strict_json_file(attestation_file)
    except FileNotFoundError as exc:
        raise ActivationError(
            ActivationErrorCode.TARGET_PUBLICATION_UNAVAILABLE
        ) from exc
    except Exception as exc:
        raise ActivationError(ActivationErrorCode.TARGET_PUBLICATION_TAMPERED) from exc
    try:
        if (
            set(attestation) != CONTROLLED_ATTESTATION_FIELDS
            or attestation["fixture_type"] != "PHASE06_CONTROLLED_ACTIVATION_FIXTURE"
            or attestation["test_only"] is not True
            or attestation["production_authority"] is not False
            or attestation["controlled_fixture_hash"]
            != expected_controlled_fixture_hash
            or attestation["status"] != "CONTROLLED_PHASE05_PUBLICATION_VERIFIED"
            or attestation["semantic_authority"] is not False
            or attestation["deployment_governance_only"] is not True
            or hashlib.sha256(raw).hexdigest() != expected_attestation_sha256
            or publication_tree_sha256(root) != expected_publication_tree_sha256
            or manifest["publication_id"] != expected_publication_id
            or manifest["publication_semantic_hash"]
            != expected_publication_semantic_hash
            or graphdb["repository_id"] != expected_repository_id
            or graphdb["assembled_dataset_semantic_hash"]
            != expected_repository_semantic_hash
            or attestation["publication_id"] != expected_publication_id
            or attestation["publication_semantic_hash"]
            != expected_publication_semantic_hash
            or attestation["repository_id"] != expected_repository_id
            or attestation["repository_semantic_hash"]
            != expected_repository_semantic_hash
        ):
            raise ValueError("controlled publication authority mismatch")
    except Exception as exc:
        raise ActivationError(ActivationErrorCode.TARGET_PUBLICATION_TAMPERED) from exc
    return {
        "publication_tree_sha256": expected_publication_tree_sha256,
        "publication_attestation_sha256": expected_attestation_sha256,
        "publication_semantic_hash": expected_publication_semantic_hash,
        "repository_semantic_hash": expected_repository_semantic_hash,
        "verification_evidence_hash": semantic_hash(
            {
                "publication_tree_sha256": expected_publication_tree_sha256,
                "publication_attestation_sha256": expected_attestation_sha256,
                "publication_semantic_hash": expected_publication_semantic_hash,
                "repository_semantic_hash": expected_repository_semantic_hash,
            }
        ),
    }


def verify_production_publication(
    *,
    package_directory: Path,
    publication_attestation_path: Path,
    publication_scenario: str,
    expected_publication_tree_sha256: str,
    expected_publication_id: str,
    expected_publication_semantic_hash: str,
    expected_repository_id: str,
    expected_repository_semantic_hash: str,
    expected_attestation_sha256: str,
) -> dict[str, Any]:
    try:
        binding = PublicationBinding.verify(
            package_directory,
            publication_attestation_path,
            publication_scenario=publication_scenario,
            expected_repository_id=expected_repository_id,
        )
        if (
            publication_tree_sha256(package_directory)
            != expected_publication_tree_sha256
            or file_sha256(publication_attestation_path) != expected_attestation_sha256
            or binding.publication_id != expected_publication_id
            or binding.publication_semantic_hash != expected_publication_semantic_hash
            or binding.repository_id != expected_repository_id
            or binding.graphdb_semantic_hash != expected_repository_semantic_hash
        ):
            raise ValueError("production publication source mismatch")
    except ActivationError:
        raise
    except FileNotFoundError as exc:
        raise ActivationError(
            ActivationErrorCode.TARGET_PUBLICATION_UNAVAILABLE
        ) from exc
    except Exception as exc:
        raise ActivationError(ActivationErrorCode.TARGET_PUBLICATION_TAMPERED) from exc
    return {
        "publication_tree_sha256": expected_publication_tree_sha256,
        "publication_attestation_sha256": expected_attestation_sha256,
        "publication_semantic_hash": expected_publication_semantic_hash,
        "repository_semantic_hash": expected_repository_semantic_hash,
        "verification_evidence_hash": semantic_hash(
            {
                "publication_tree_sha256": expected_publication_tree_sha256,
                "publication_attestation_sha256": expected_attestation_sha256,
                "publication_semantic_hash": expected_publication_semantic_hash,
                "repository_semantic_hash": expected_repository_semantic_hash,
            }
        ),
    }
