from __future__ import annotations

from pathlib import Path

import pytest

from kg_mnp.workspace.service import WorkspaceError, initialize_workspace
from kg_mnp.workspace.validation import validate_workspace
from tests.workspace.conftest import ROOT


def test_workspace_symlink_escape_is_rejected_or_explicitly_skipped(workspace_path: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link = workspace_path / "sources" / "escape.txt"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"platform cannot create test symlink: {exc}")
    result = validate_workspace(workspace_path, domain_packs_root=ROOT / "domain_packs")
    assert result.status == "INVALID"
    assert "symlink" in " ".join(item["message"] for item in result.report["checks"]).casefold()


def test_workspace_identifier_attacks_do_not_create_targets(tmp_path: Path) -> None:
    for project_id in ("../escape", "C-drive", "has space", "project.name"):
        target = tmp_path / project_id.replace("/", "-")
        with pytest.raises((ValueError, WorkspaceError)):
            initialize_workspace(
                target,
                project_id=project_id,
                project_version="0.1.0",
                display_name="Unsafe",
                domain_pack="minimal",
                domain_pack_version="0.1.0",
                domain_packs_root=ROOT / "domain_packs",
            )
        assert not target.exists()


def test_duplicate_yaml_key_unsafe_tag_non_utf8_and_oversize_fail_closed(workspace_path: Path) -> None:
    manifest = workspace_path / "project.yaml"
    attacks = [
        b"manifest_kind: KG_MNP_PROJECT\nmanifest_kind: DUPLICATE\n",
        b"manifest_kind: !!python/object/apply:os.system ['unsafe']\n",
        b"\xff\xfe",
        b"x" * (1024 * 1024 + 1),
    ]
    for payload in attacks:
        manifest.write_bytes(payload)
        result = validate_workspace(workspace_path, domain_packs_root=ROOT / "domain_packs")
        assert result.status == "INVALID"

