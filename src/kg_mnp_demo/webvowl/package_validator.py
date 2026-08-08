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
from ..modeling.dependencies import ROOT
from .package_builder import build_webvowl_visualization_package


class WebVOWLPackageValidationError(ValueError):
    pass


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise WebVOWLPackageValidationError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def validate_webvowl_visualization_package(
    package_directory: Path, *, root: Path = ROOT, **kwargs: Any
) -> dict[str, Any]:
    try:
        directory = validated_directory(
            Path(package_directory), label="visualization package"
        )
    except UnsafePathError as exc:
        raise WebVOWLPackageValidationError(str(exc)) from exc
    expected = build_webvowl_visualization_package(
        root=root,
        ontology_baseline=kwargs.get("ontology_baseline"),
        graphdb_tbox_semantic_hash=kwargs.get("graphdb_tbox_semantic_hash"),
    )
    try:
        expected_paths = set(expected["files"])
        for relative in expected_paths:
            safe_artifact_path(
                directory, relative, label="expected visualization artifact"
            )
        actual_paths = set(
            closed_regular_files(directory, label="visualization package")
        )
        actual_manifest = safe_artifact_path(
            directory,
            "visualization/visualization-manifest.json",
            label="visualization manifest",
        )
    except UnsafePathError as exc:
        raise WebVOWLPackageValidationError(str(exc)) from exc
    actual = json.loads(
        actual_manifest.read_text(encoding="utf-8"), object_pairs_hook=_unique
    )
    if actual != expected["manifest"]:
        raise WebVOWLPackageValidationError(
            "visualization manifest reconstruction mismatch"
        )
    if actual_paths != expected_paths:
        raise WebVOWLPackageValidationError(
            "visualization closed artifact set mismatch"
        )
    for rel, data in expected["files"].items():
        try:
            path = safe_artifact_path(directory, rel, label="visualization artifact")
        except UnsafePathError as exc:
            raise WebVOWLPackageValidationError(str(exc)) from exc
        if path.read_bytes() != data:
            raise WebVOWLPackageValidationError(
                f"visualization artifact bytes mismatch: {rel}"
            )
    return {
        "valid": True,
        "deterministic_reconstruction_match": True,
        "release_status": actual["release_status"],
        "visualization_id": actual["visualization_id"],
    }
