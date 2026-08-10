#!/usr/bin/env python3
"""Verify a downloaded Application Phase 02 artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kg_mnp_demo.workbench.artifact_verifier import (
    verify_application_phase02_artifact,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_directory")
    arguments = parser.parse_args()
    result = verify_application_phase02_artifact(Path(arguments.artifact_directory))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
