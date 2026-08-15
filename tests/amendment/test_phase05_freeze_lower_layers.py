from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHASE04_INPUT_HEAD = "3254656ffcd1c42b601d30b6ea313c6f81642bef"
FROZEN = (
    "ontology",
    "shapes",
    "schemas/modeling",
    "schemas/compilation",
    "schemas/graphdb",
    "schemas/webvowl",
    "schemas/publication",
    "config/modeling",
    "config/compilation",
    "config/graphdb",
    "config/webvowl",
    "config/application",
    "config/workbench",
    "config/diagnostics",
    "schemas/application",
    "schemas/workbench",
    "schemas/diagnostics",
    "src/kg_mnp_demo/modeling",
    "src/kg_mnp_demo/compilation",
    "src/kg_mnp_demo/graphdb",
    "src/kg_mnp_demo/webvowl",
    "src/kg_mnp_demo/publication",
    "src/kg_mnp_demo/application",
    "src/kg_mnp_demo/workbench",
    "src/kg_mnp_demo/diagnostics",
    "src/kg_mnp_demo/governance",
    "tests/application",
    "tests/workbench",
    "tests/diagnostics",
    "tests/application_governance",
    "scripts/verify_application_phase04_artifact.py",
)


def test_foundation_and_phases01_to04_are_frozen() -> None:
    changed = subprocess.run(
        ["git", "diff", "--name-only", PHASE04_INPUT_HEAD, "--", *FROZEN],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", *FROZEN],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert changed + untracked == []
