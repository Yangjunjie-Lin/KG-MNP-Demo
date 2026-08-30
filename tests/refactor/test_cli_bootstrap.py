from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import kg_mnp

ROOT = Path(__file__).resolve().parents[2]


def _environment(workspace: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["KG_MNP_WORKSPACE"] = str(workspace)
    return environment


def test_python_module_help_is_read_only_and_offline(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    result = subprocess.run(
        [sys.executable, "-m", "kg_mnp", "--help"],
        cwd=tmp_path,
        env=_environment(workspace),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.casefold()
    assert not workspace.exists()


def test_installed_console_help_is_read_only_and_offline(tmp_path: Path) -> None:
    executable = shutil.which("kg-mnp")
    assert executable is not None
    workspace = tmp_path / "workspace"
    result = subprocess.run(
        [executable, "--help"],
        cwd=tmp_path,
        env=_environment(workspace),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.casefold()
    assert not workspace.exists()


def test_import_has_no_runtime_side_effect(tmp_path: Path) -> None:
    assert kg_mnp.__name__ == "kg_mnp"
    assert list(tmp_path.iterdir()) == []
