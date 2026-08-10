#!/usr/bin/env python3
"""Independently verify an Application Phase 01 CI artifact directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kg_mnp_demo.application.artifact_verifier import (
    ArtifactVerificationError,
    verify_application_phase01_artifact,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_directory", type=Path)
    args = parser.parse_args()
    try:
        result = verify_application_phase01_artifact(args.artifact_directory)
    except ArtifactVerificationError as exc:
        print(json.dumps({"status": "FAILED", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
