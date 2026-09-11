from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path

from packaging.version import Version

import kg_mnp

ROOT = Path(__file__).resolve().parents[2]


def test_source_package_identity() -> None:
    assert kg_mnp.__name__ == "kg_mnp"
    assert str(Version(kg_mnp.__version__)) == kg_mnp.__version__
    assert not (ROOT / "src" / ("kg_" + "mnp_demo")).exists()


def test_distribution_metadata_and_console_surface() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    assert project["name"] == "zhigou-toolchain"
    assert "version" in project["dynamic"]
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["tool"]["setuptools"]["dynamic"]["version"]["attr"] == "zhigou_toolchain.__version__"
    expected_scripts = {"zhigou-toolchain": "zhigou_toolchain.root_cli:main", "kg-mnp": "kg_mnp:legacy_main"}
    assert project["scripts"] == expected_scripts

    distribution = importlib.metadata.distribution("zhigou-toolchain")
    assert distribution.version == kg_mnp.__version__
    console_scripts = {
        entry.name: entry.value
        for entry in distribution.entry_points
        if entry.group == "console_scripts"
    }
    assert console_scripts == expected_scripts
    assert "kg-mnp-eligibility" not in console_scripts
