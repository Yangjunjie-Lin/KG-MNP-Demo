#!/usr/bin/env python3
"""Verify an extracted Application Phase 06 artifact independently."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kg_mnp_demo._path_security import UnsafePathError
from kg_mnp_demo.activation.artifact_verifier import (
    Phase06ArtifactVerificationError,
    verify_application_phase06_artifact,
)
from kg_mnp_demo.activation.errors import ActivationError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("--publication-package", required=True, type=Path)
    parser.add_argument("--publication-attestation", required=True, type=Path)
    parser.add_argument("--publication-scenario", required=True)
    parser.add_argument("--phase01-artifact-dir", required=True, type=Path)
    parser.add_argument("--phase02-artifact-dir", required=True, type=Path)
    parser.add_argument("--phase03-artifact-dir", required=True, type=Path)
    parser.add_argument("--phase04-artifact-dir", required=True, type=Path)
    parser.add_argument("--phase05-artifact-dir", required=True, type=Path)
    parser.add_argument("--expected-commit-sha", required=True)
    parser.add_argument("--expected-registry-hash", required=True)
    parser.add_argument("--expected-head-event-hash", required=True)
    arguments = parser.parse_args()
    try:
        result = verify_application_phase06_artifact(
            arguments.artifact_directory,
            publication_package_directory=arguments.publication_package,
            publication_attestation_path=arguments.publication_attestation,
            publication_scenario=arguments.publication_scenario,
            phase01_artifact_directory=arguments.phase01_artifact_dir,
            phase02_artifact_directory=arguments.phase02_artifact_dir,
            phase03_artifact_directory=arguments.phase03_artifact_dir,
            phase04_artifact_directory=arguments.phase04_artifact_dir,
            phase05_artifact_directory=arguments.phase05_artifact_dir,
            expected_commit_sha=arguments.expected_commit_sha,
            expected_registry_hash=arguments.expected_registry_hash,
            expected_head_event_hash=arguments.expected_head_event_hash,
        )
    except (
        ActivationError,
        Phase06ArtifactVerificationError,
        UnsafePathError,
        ValueError,
        TypeError,
        OSError,
    ) as exc:
        print(json.dumps({"status": "FAILED", "detail": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
