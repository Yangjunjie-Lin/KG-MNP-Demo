from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path

import kg_mnp

ROOT = Path(__file__).resolve().parents[2]


def test_source_package_identity() -> None:
    assert kg_mnp.__name__ == "kg_mnp"
    assert kg_mnp.__version__ == "0.2.0.dev0"
    assert not (ROOT / "src" / ("kg_" + "mnp_demo")).exists()


def test_distribution_metadata_and_console_surface() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    assert project["name"] == "kg-mnp-toolchain"
    assert project["version"] == "0.2.0.dev0"
    assert project["scripts"] == {"kg-mnp": "kg_mnp.root_cli:main"}

    distribution = importlib.metadata.distribution("kg-mnp-toolchain")
    assert distribution.version == "0.2.0.dev0"
    console_scripts = {
        entry.name: entry.value
        for entry in distribution.entry_points
        if entry.group == "console_scripts"
    }
    assert console_scripts == {"kg-mnp": "kg_mnp.root_cli:main"}
    assert "kg-mnp-eligibility" not in console_scripts
