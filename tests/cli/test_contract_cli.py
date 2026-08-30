from __future__ import annotations

import json
from pathlib import Path

from kg_mnp import root_cli

ROOT = Path(__file__).resolve().parents[2]


def test_contract_help_list_show_and_catalog_smokes(capsys) -> None:
    assert root_cli.main(["contracts", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert len(listed["result"]) == 34
    assert listed["command"] == "contracts list"
    assert root_cli.main(["contracts", "show", "domain-pack-manifest"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["title"] == "KG-MNP DomainPackManifest 1.0"
    assert root_cli.main(["contracts", "verify-catalog", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "VALID"


def test_contract_validation_supports_new_and_legacy_syntax(capsys) -> None:
    path = ROOT / "domain_packs" / "minimal" / "pack.yaml"
    assert root_cli.main(["contracts", "validate", "domain-pack-manifest", str(path)]) == 0
    capsys.readouterr()
    assert root_cli.main(["contracts", "validate", "--contract", "domain-pack-manifest", "--input", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "VALID"


def test_contract_invalid_and_document_security_have_stable_nonzero_codes(tmp_path: Path, capsys) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("manifest_kind: WRONG\n", encoding="utf-8")
    assert root_cli.main(["contracts", "validate", "project-manifest", str(invalid), "--json"]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["code"] == 3
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text("x: 1\nx: 2\n", encoding="utf-8")
    assert root_cli.main(["contracts", "validate", "project-manifest", str(duplicate)]) == 4
    assert "Traceback" not in capsys.readouterr().err
