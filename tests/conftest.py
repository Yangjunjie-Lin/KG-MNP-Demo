from __future__ import annotations

from pathlib import Path

import pytest

from kg_mnp.workspace.service import initialize_workspace

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def prompt03_workspace(tmp_path: Path) -> Path:
    target = tmp_path / "workspace"
    initialize_workspace(
        target,
        project_id="prompt03-test-project",
        project_version="0.3.0",
        display_name="Prompt 3 Test Project",
        domain_pack="minimal",
        domain_pack_version="0.1.0",
        domain_packs_root=ROOT / "domain_packs",
    )
    return target
