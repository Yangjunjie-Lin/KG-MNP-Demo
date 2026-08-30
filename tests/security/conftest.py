from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from kg_mnp.workspace.service import initialize_workspace

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def minimal_copy(tmp_path: Path) -> Path:
    destination = tmp_path / "minimal"
    shutil.copytree(ROOT / "domain_packs" / "minimal", destination)
    return destination


@pytest.fixture
def workspace_path(tmp_path: Path) -> Path:
    target = tmp_path / "workspace"
    initialize_workspace(
        target,
        project_id="minimal-contract-project",
        project_version="0.1.0",
        display_name="Minimal Contract Project",
        domain_pack="minimal",
        domain_pack_version="0.1.0",
        domain_packs_root=ROOT / "domain_packs",
    )
    return target
