from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from kg_mnp.contracts.registry import validate_contract
from kg_mnp.domain_packs.registry import DomainPackRegistry, DomainPackRegistryError
from kg_mnp.workspace.layout import DIRECTORIES
from kg_mnp.workspace.locking import ProjectLockError, generate_project_lock
from kg_mnp.workspace.service import (
    WorkspaceError,
    initialize_workspace,
    load_project_manifest,
    open_workspace,
)
from kg_mnp.workspace.validation import validate_workspace

from .conftest import ROOT


def _init(target: Path, *, display_name: str = "Minimal Contract Project"):
    return initialize_workspace(
        target,
        project_id="minimal-contract-project",
        project_version="0.1.0",
        display_name=display_name,
        domain_pack="minimal",
        domain_pack_version="0.1.0",
        domain_packs_root=ROOT / "domain_packs",
    )


def test_init_new_and_empty_directories_build_exact_layout_and_valid_contracts(tmp_path: Path) -> None:
    for target in (tmp_path / "new", tmp_path / "empty"):
        if target.name == "empty":
            target.mkdir()
        workspace = _init(target, display_name="最小契约项目")
        assert workspace.root == target.absolute()
        assert all((target / relative).is_dir() for relative in DIRECTORIES)
        assert not any((target / "artifacts" / "confirmed").iterdir())
        validate_contract("project-manifest", workspace.manifest.document)
        validate_contract("project-lock", workspace.lock.document)
        assert validate_workspace(target, domain_packs_root=ROOT / "domain_packs").valid
        assert open_workspace(target).manifest.document["display_name"] == "最小契约项目"


def test_init_refuses_nonempty_directory_and_failure_leaves_no_half_workspace(tmp_path: Path) -> None:
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    marker = nonempty / "user.txt"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="non-empty"):
        _init(nonempty)
    assert marker.read_text(encoding="utf-8") == "preserve"

    failed = tmp_path / "failed"
    with pytest.raises(DomainPackRegistryError):
        initialize_workspace(
            failed,
            project_id="minimal-contract-project",
            project_version="0.1.0",
            display_name="Failure",
            domain_pack="missing",
            domain_pack_version="0.1.0",
            domain_packs_root=ROOT / "domain_packs",
        )
    assert not failed.exists()
    assert not list(tmp_path.glob(".failed.kg-mnp-init-*"))


def test_project_lock_is_deterministic_check_only_and_path_independent(tmp_path: Path) -> None:
    first = _init(tmp_path / "one")
    second = _init(tmp_path / "two")
    assert first.lock.path.read_bytes() == second.lock.path.read_bytes()
    before = first.lock.path.read_bytes()
    registry = DomainPackRegistry(ROOT / "domain_packs")
    assert generate_project_lock(first.manifest, registry, check=True).path.read_bytes() == before
    assert str(first.root).encode() not in before
    assert b"generated_at" not in before


def test_project_manifest_change_makes_lock_stale_and_regeneration_restores_it(workspace_path: Path) -> None:
    path = workspace_path / "project.yaml"
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    value["description"] = "Changed project description."
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    result = validate_workspace(workspace_path, domain_packs_root=ROOT / "domain_packs")
    assert result.status == "STALE_PROJECT_LOCK"
    manifest = load_project_manifest(workspace_path)
    registry = DomainPackRegistry(ROOT / "domain_packs")
    with pytest.raises(ProjectLockError):
        generate_project_lock(manifest, registry, check=True)
    generate_project_lock(manifest, registry)
    assert validate_workspace(workspace_path, domain_packs_root=ROOT / "domain_packs").valid


def test_reports_and_tmp_are_non_authoritative_and_do_not_change_lock(workspace_path: Path) -> None:
    before = (workspace_path / "project.lock.json").read_bytes()
    (workspace_path / "reports" / "human.txt").write_text("non-authoritative", encoding="utf-8")
    (workspace_path / "tmp" / "scratch.bin").write_bytes(b"temporary")
    assert validate_workspace(workspace_path, domain_packs_root=ROOT / "domain_packs").valid
    assert (workspace_path / "project.lock.json").read_bytes() == before


def test_dependency_resolution_is_reflected_in_project_lock(tmp_path: Path) -> None:
    packs = tmp_path / "packs"
    shutil.copytree(ROOT / "domain_packs", packs)
    base_lock = yaml.safe_load((packs / "minimal" / "pack.yaml").read_text(encoding="utf-8"))
    assert base_lock["pack_id"] == "minimal"
    workspace = initialize_workspace(
        tmp_path / "dependent-workspace",
        project_id="dependent-project",
        project_version="0.1.0",
        display_name="Dependent Project",
        domain_pack="minimal",
        domain_pack_version="0.1.0",
        domain_packs_root=packs,
    )
    assert [(item["pack_id"], item["dependency_depth"]) for item in workspace.lock.document["resolved_domain_packs"]] == [("minimal", 0)]
