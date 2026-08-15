#!/usr/bin/env python3
"""Verify an extracted Application Phase 05 artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kg_mnp_demo.amendment.artifact_verifier import (
    Phase05ArtifactVerificationError,
    verify_application_phase05_artifact,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("--stage08-artifact", required=True, type=Path)
    parser.add_argument("--publication-attestation", type=Path)
    parser.add_argument("--phase01-artifact", required=True, type=Path)
    parser.add_argument("--phase02-artifact", required=True, type=Path)
    parser.add_argument("--phase03-artifact", required=True, type=Path)
    parser.add_argument("--phase04-artifact", required=True, type=Path)
    parser.add_argument("--expected-commit-sha", required=True)
    parser.add_argument("--publication-scenario", default="full-confirmation")
    args = parser.parse_args()
    try:
        result = verify_application_phase05_artifact(
            args.artifact_directory,
            stage08_artifact=args.stage08_artifact,
            publication_attestation=args.publication_attestation,
            phase01_artifact=args.phase01_artifact,
            phase02_artifact=args.phase02_artifact,
            phase03_artifact=args.phase03_artifact,
            phase04_artifact=args.phase04_artifact,
            expected_commit_sha=args.expected_commit_sha,
            publication_scenario=args.publication_scenario,
        )
    except (Phase05ArtifactVerificationError, ValueError, OSError) as exc:
        print(json.dumps({"status": "FAILED", "detail": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
