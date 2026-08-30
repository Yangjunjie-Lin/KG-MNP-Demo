from __future__ import annotations

from pathlib import Path

import pytest

from kg_mnp.workspace.service import initialize_workspace

ROOT = Path(__file__).resolve().parents[2]


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

