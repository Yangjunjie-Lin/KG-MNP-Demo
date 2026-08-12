from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STAGE08 = "4dc09d9cfb15da3746f108755593ceb9fe805cd7"
PHASE01 = "79b7d34125b0c5cb2d5fe8546e1f4e6a95ca8106"
PHASE02 = "3ef40b9cfbd657b55d8c5f446cfc247335db87f0"
PHASE03 = "06898e8ef3fbe93bd7e7a030f4361c0bef7a76c9"
FOUNDATION = (
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
    "src/kg_mnp_demo/modeling",
    "src/kg_mnp_demo/review",
    "src/kg_mnp_demo/compilation",
    "src/kg_mnp_demo/graphdb",
    "src/kg_mnp_demo/webvowl",
    "src/kg_mnp_demo/publication",
)
PHASE01_PATHS = (
    "config/application",
    "queries/application",
    "schemas/application",
    "src/kg_mnp_demo/application",
    "examples/application",
    "tests/application",
    "scripts/application_integration.py",
    "scripts/verify_application_phase01_artifact.py",
)
PHASE02_PATHS = (
    "config/workbench",
    "schemas/workbench",
    "src/kg_mnp_demo/workbench",
    "web/workbench",
    "tests/workbench",
    "scripts/workbench_integration.py",
    "scripts/verify_application_phase02_artifact.py",
)
PHASE03_PATHS = (
    "schemas/diagnostics",
    "src/kg_mnp_demo/diagnostics",
    "web/diagnostics",
    "tests/diagnostics",
    "scripts/diagnostics_integration.py",
    "scripts/verify_application_phase03_artifact.py",
)


def changed(baseline: str, paths: tuple[str, ...]) -> list[str]:
    diff = subprocess.run(
        ["git", "diff", "--name-only", baseline, "--", *paths],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", *paths],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return [*diff, *untracked]


def test_all_lower_layers_are_frozen() -> None:
    assert changed(STAGE08, FOUNDATION) == []
    assert changed(PHASE01, PHASE01_PATHS) == []
    assert changed(PHASE02, PHASE02_PATHS) == []
    assert changed(PHASE03, PHASE03_PATHS) == []
