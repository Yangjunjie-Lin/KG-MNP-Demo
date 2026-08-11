#!/usr/bin/env python3
"""Verify an extracted Application Phase 03 CI artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kg_mnp_demo.diagnostics.artifact_verifier import (
    DiagnosticArtifactVerificationError,
    verify_application_phase03_artifact,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("--expected-commit-sha")
    arguments = parser.parse_args()
    try:
        result = verify_application_phase03_artifact(
            arguments.artifact_directory,
            expected_commit_sha=arguments.expected_commit_sha,
        )
    except DiagnosticArtifactVerificationError as exc:
        print(json.dumps({"status": "FAILED", "detail": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
