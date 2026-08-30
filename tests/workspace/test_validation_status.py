from __future__ import annotations

import json
import shutil
from pathlib import Path

from kg_mnp.workspace.status import ALL_STATUSES
from kg_mnp.workspace.validation import validate_workspace

from .conftest import ROOT


def test_all_documented_status_values_are_exposed() -> None:
    assert set(ALL_STATUSES) == {
        "UNINITIALIZED", "VALID", "INVALID", "STALE_PROJECT_LOCK",
        "STALE_DOMAIN_PACK_LOCK", "MISSING_DOMAIN_PACK", "CONTRACT_CATALOG_MISMATCH",
    }


def test_uninitialized_and_missing_lock_statuses(tmp_path: Path, workspace_path: Path) -> None:
    assert validate_workspace(tmp_path / "absent").status == "UNINITIALIZED"
    (workspace_path / "project.lock.json").unlink()
    assert validate_workspace(workspace_path, domain_packs_root=ROOT / "domain_packs").status == "STALE_PROJECT_LOCK"


def test_missing_pack_and_stale_pack_lock_are_distinguished(tmp_path: Path, workspace_path: Path) -> None:
    empty = tmp_path / "empty-packs"
    empty.mkdir()
    assert validate_workspace(workspace_path, domain_packs_root=empty).status == "MISSING_DOMAIN_PACK"

    packs = tmp_path / "packs"
    shutil.copytree(ROOT / "domain_packs", packs)
    with (packs / "minimal" / "ontology" / "minimal.ttl").open("a", encoding="utf-8") as stream:
        stream.write("\n# lock-changing but valid comment\n")
    assert validate_workspace(workspace_path, domain_packs_root=packs).status == "STALE_DOMAIN_PACK_LOCK"


def test_contract_catalog_mismatch_is_distinguished(workspace_path: Path) -> None:
    path = workspace_path / "project.lock.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["contract_catalog_digest"] = "0" * 64
    path.write_text(json.dumps(value), encoding="utf-8")
    assert validate_workspace(workspace_path, domain_packs_root=ROOT / "domain_packs").status == "CONTRACT_CATALOG_MISMATCH"


def test_unexpected_top_level_and_confirmed_authority_are_invalid(workspace_path: Path) -> None:
    (workspace_path / "authority.ttl").write_text("@prefix x: <urn:x:> .", encoding="utf-8")
    (workspace_path / "artifacts" / "confirmed" / "bypass.ttl").write_text("@prefix x: <urn:x:> .", encoding="utf-8")
    result = validate_workspace(workspace_path, domain_packs_root=ROOT / "domain_packs")
    assert result.status == "INVALID"
    assert {item["code"] for item in result.report["checks"]} >= {
        "UNEXPECTED_AUTHORITY_ENTRY", "UNEXPECTED_CONFIRMED_AUTHORITY"
    }

