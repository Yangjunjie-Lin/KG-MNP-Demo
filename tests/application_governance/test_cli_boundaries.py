from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(*arguments: str):
    return subprocess.run(
        [sys.executable, "-m", "kg_mnp_demo.root_cli", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_root_cli_exposes_only_governance_lifecycle_commands() -> None:
    help_result = run("governance", "--help")
    assert help_result.returncode == 0
    assert "initialize" in help_result.stdout
    assert "verify" in help_result.stdout
    assert "proposal" in help_result.stdout
    assert "inspect" in help_result.stdout
    assert "serve" in help_result.stdout
    for forbidden in ("graph patch", "rdf update", "repair", "resolve"):
        assert forbidden not in help_result.stdout.casefold()


def test_unavailable_mutation_commands_fail_closed() -> None:
    for command in ("repair", "resolve", "graph", "rdf"):
        result = run("governance", command)
        assert result.returncode != 0
