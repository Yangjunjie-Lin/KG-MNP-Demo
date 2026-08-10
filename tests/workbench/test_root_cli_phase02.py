from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from kg_mnp_demo.workbench.artifact_verifier import ARTIFACT_FILES

from ._helpers import write_phase01_artifact


ROOT = Path(__file__).resolve().parents[2]


def run_cli(*arguments: str):
    return subprocess.run(
        [sys.executable, "-m", "kg_mnp_demo.root_cli", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_root_cli_exposes_only_read_only_workbench_commands() -> None:
    result = run_cli("workbench", "--help")
    assert result.returncode == 0
    assert "package" in result.stdout
    assert "runtime" in result.stdout
    assert "serve" in result.stdout
    for forbidden in ("write", "review", "approve", "update"):
        assert forbidden not in result.stdout.casefold()


def test_cli_builds_and_validates_deterministic_package(tmp_path) -> None:
    artifact = write_phase01_artifact(tmp_path / "phase01")
    package = tmp_path / "package"
    build = run_cli(
        "workbench",
        "package",
        "build",
        "--phase01-artifact-dir",
        str(artifact),
        "--output-dir",
        str(package),
    )
    assert build.returncode == 0, build.stdout + build.stderr
    validate = run_cli(
        "workbench",
        "package",
        "validate",
        "--phase01-artifact-dir",
        str(artifact),
        "--package-dir",
        str(package),
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr
    assert "WORKBENCH_PACKAGE_VALIDATED" in validate.stdout
    assert ARTIFACT_FILES.isdisjoint(path.name for path in package.rglob("*"))
