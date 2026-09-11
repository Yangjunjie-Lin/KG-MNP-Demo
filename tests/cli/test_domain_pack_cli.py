from __future__ import annotations

import json
import shutil
from pathlib import Path

from kg_mnp import root_cli

ROOT = Path(__file__).resolve().parents[2]


def test_domain_pack_list_inspect_validate_lock_and_json_smokes(capsys) -> None:
    packs = str(ROOT / "domain_packs")
    assert root_cli.main(["domain-pack", "list", "--domain-packs-root", packs, "--json"]) == 0
    assert [item["pack_id"] for item in json.loads(capsys.readouterr().out)["result"]] == ["empty", "forestry", "forestry-workorders", "forestry-workorders", "hr", "minimal", "mnp"]
    for pack in ("minimal", "mnp", "forestry"):
        path = str(ROOT / "domain_packs" / pack)
        assert root_cli.main(["domain-pack", "inspect", path, "--json"]) == 0
        capsys.readouterr()
        assert root_cli.main(["domain-pack", "validate", path]) == 0
        capsys.readouterr()
        assert root_cli.main(["domain-pack", "verify-lock", path]) == 0
        capsys.readouterr()
        assert root_cli.main(["domain-pack", "lock", path, "--check"]) == 0
        capsys.readouterr()


def test_domain_pack_path_with_spaces_and_lock_mismatch_exit(tmp_path: Path, capsys) -> None:
    target = tmp_path / "packs with spaces" / "minimal"
    shutil.copytree(ROOT / "domain_packs" / "minimal", target)
    assert root_cli.main(["domain-pack", "validate", str(target), "--json"]) == 0
    capsys.readouterr()
    with (target / "ontology" / "minimal.ttl").open("a", encoding="utf-8") as stream:
        stream.write("\n# changed\n")
    assert root_cli.main(["domain-pack", "verify-lock", str(target)]) == 5
    assert "Traceback" not in capsys.readouterr().err


def test_domain_pack_security_failure_exit(tmp_path: Path, capsys) -> None:
    target = tmp_path / "minimal"
    shutil.copytree(ROOT / "domain_packs" / "minimal", target)
    (target / "payload.py").write_text("raise SystemExit", encoding="utf-8")
    assert root_cli.main(["domain-pack", "validate", str(target), "--json"]) == 4
    assert json.loads(capsys.readouterr().out)["code"] == 4

