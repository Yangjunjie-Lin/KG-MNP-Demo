from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .._path_security import (
    UnsafePathError,
    closed_regular_files,
    safe_artifact_path,
    validated_directory,
)
from .package_builder import build_end_to_end_publication_package


class PublicationPackageValidationError(ValueError):
    pass


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise PublicationPackageValidationError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def validate_end_to_end_publication_package_against_authorities(
    package_directory: Path, **kwargs: Any
) -> dict[str, Any]:
    try:
        directory = validated_directory(
            Path(package_directory), label="publication package"
        )
    except UnsafePathError as exc:
        raise PublicationPackageValidationError(str(exc)) from exc
    expected = build_end_to_end_publication_package(**kwargs)
    try:
        expected_paths = set(expected["files"])
        for relative in expected_paths:
            safe_artifact_path(
                directory, relative, label="expected publication artifact"
            )
        actual_paths = set(closed_regular_files(directory, label="publication package"))
        manifest_path = safe_artifact_path(
            directory,
            "publication-manifest.json",
            label="publication manifest",
        )
    except UnsafePathError as exc:
        raise PublicationPackageValidationError(str(exc)) from exc
    actual = json.loads(
        manifest_path.read_text(encoding="utf-8"), object_pairs_hook=_unique
    )
    if actual != expected["manifest"]:
        raise PublicationPackageValidationError(
            "publication manifest does not match reconstructed authorities"
        )
    if actual_paths != expected_paths:
        raise PublicationPackageValidationError(
            "publication closed artifact set mismatch"
        )
    for relative, data in expected["files"].items():
        try:
            path = safe_artifact_path(directory, relative, label="publication artifact")
        except UnsafePathError as exc:
            raise PublicationPackageValidationError(str(exc)) from exc
        if path.read_bytes() != data:
            raise PublicationPackageValidationError(
                f"publication artifact bytes mismatch: {relative}"
            )
    return {
        "valid": True,
        "deterministic_reconstruction_match": True,
        "publication_status": "READY_FOR_PRESENTATION",
        "publication_id": actual["publication_id"],
    }
