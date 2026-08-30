from __future__ import annotations

import json
from pathlib import Path

from kg_mnp import root_cli

ROOT = Path(__file__).resolve().parents[2]


def _init(target: Path, capsys) -> None:
    assert root_cli.main([
        "workspace", "init", str(target),
        "--project-id", "minimal-contract-project",
        "--project-version", "0.1.0",
        "--display-name", "最小 Contract Project",
        "--domain-pack", "minimal",
        "--domain-pack-version", "0.1.0",
        "--domain-packs-root", str(ROOT / "domain_packs"),
        "--json",
    ]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["status"] == "VALID"


def test_workspace_init_validate_status_inspect_and_lock_smokes(tmp_path: Path, capsys) -> None:
    target = tmp_path / "workspace with spaces"
    _init(target, capsys)
    for command in ("validate", "status", "inspect"):
        assert root_cli.main(["workspace", command, str(target), "--domain-packs-root", str(ROOT / "domain_packs"), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["code"] == 0
    assert root_cli.main(["workspace", "lock", str(target), "--domain-packs-root", str(ROOT / "domain_packs"), "--check", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "VALID"


def test_workspace_nonempty_and_stale_lock_have_stable_codes(tmp_path: Path, capsys) -> None:
    target = tmp_path / "workspace"
    target.mkdir()
    (target / "user.txt").write_text("preserve", encoding="utf-8")
    result = root_cli.main([
        "workspace", "init", str(target),
        "--project-id", "minimal-contract-project",
        "--project-version", "0.1.0",
        "--display-name", "Minimal",
        "--domain-pack", "minimal",
        "--domain-pack-version", "0.1.0",
        "--domain-packs-root", str(ROOT / "domain_packs"),
    ])
    assert result == 7
    assert "Traceback" not in capsys.readouterr().err

    valid = tmp_path / "valid"
    _init(valid, capsys)
    (valid / "project.lock.json").unlink()
    assert root_cli.main(["workspace", "validate", str(valid), "--domain-packs-root", str(ROOT / "domain_packs")]) == 5
    capsys.readouterr()
    assert root_cli.main(["workspace", "lock", str(valid), "--domain-packs-root", str(ROOT / "domain_packs"), "--check"]) == 5

