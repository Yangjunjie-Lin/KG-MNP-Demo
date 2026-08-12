#!/usr/bin/env python3
"""Verify a Phase04 artifact using independently reconstructed Phase03 authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kg_mnp_demo.diagnostics.engine import AuthoritySnapshot
from kg_mnp_demo.governance.artifact_verifier import (
    Phase04ArtifactVerificationError,
    verify_application_phase04_artifact,
)
from kg_mnp_demo.governance.authority_binding import load_verified_phase03_authority
from kg_mnp_demo.governance.contracts import strict_json_file
from kg_mnp_demo.governance.errors import GovernanceError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("--diagnostic-package", required=True, type=Path)
    parser.add_argument("--phase03-attestation", required=True, type=Path)
    parser.add_argument("--authority-snapshot", required=True, type=Path)
    parser.add_argument("--expected-commit-sha")
    parser.add_argument("--expected-workspace-hash", required=True)
    arguments = parser.parse_args()
    try:
        authority = load_verified_phase03_authority(
            diagnostic_package=arguments.diagnostic_package,
            phase03_attestation=arguments.phase03_attestation,
            authority_snapshot=AuthoritySnapshot.from_dict(
                strict_json_file(arguments.authority_snapshot)
            ),
        )
        result = verify_application_phase04_artifact(
            arguments.artifact_directory,
            authority=authority,
            expected_commit_sha=arguments.expected_commit_sha,
            expected_workspace_hash=arguments.expected_workspace_hash,
        )
    except (
        GovernanceError,
        Phase04ArtifactVerificationError,
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
