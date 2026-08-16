from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHASE06_INPUT_HEAD = "9e7684bb9b988cec796e86ed9a6c51c59fa3a741"

FROZEN = (
    "src/kg_mnp_demo",
    "schemas",
    "config",
    "ontology",
    "shapes",
    "data",
    "rules",
    "mappings",
    "queries",
    "competency_questions",
    "deploy",
    "scripts",
    "tests",
    "web",
    ":(exclude)src/kg_mnp_demo/activation",
    ":(exclude)src/kg_mnp_demo/root_cli.py",
    ":(exclude)schemas/activation",
    ":(exclude)scripts/activation_controlled_fixture.py",
    ":(exclude)scripts/activation_integration.py",
    ":(exclude)scripts/verify_application_phase06_artifact.py",
    ":(exclude)tests/activation",
)


def _lines(*arguments: str) -> list[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()


def test_foundation_and_application_phases01_to05_are_frozen() -> None:
    changed = _lines("diff", "--name-only", PHASE06_INPUT_HEAD, "--", *FROZEN)
    untracked = _lines("ls-files", "--others", "--exclude-standard", "--", *FROZEN)
    assert changed + untracked == []
