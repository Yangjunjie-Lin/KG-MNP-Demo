from __future__ import annotations

import json
from pathlib import Path

from kg_mnp.semantic_kernel.cli import package_main

ROOT = Path(__file__).resolve().parents[2]


def _run(arguments: list[str], capsys) -> dict:
    assert package_main(arguments) == 0
    return json.loads(capsys.readouterr().out)


def test_package_list_inspect_verify_export_archive_and_contents_cli(prompt05_case: dict, capsys) -> None:
    workspace = str(prompt05_case["workspace"])
    package_id = prompt05_case["result"].package_id
    listing = _run(["list", workspace, "--json"], capsys)
    assert [row["package_id"] for row in listing["result"]] == [package_id]
    inspected = _run(["inspect", workspace, package_id, "--json"], capsys)
    assert inspected["result"]["package_status"] == "VALIDATED_UNPUBLISHED"
    verified = _run(["verify", workspace, package_id, "--json"], capsys)
    assert verified["result"]["status"] == "VALID"
    exported = _run(
        [
            "export",
            workspace,
            package_id,
            "--domain-packs-root",
            str(ROOT / "domain_packs"),
            "--reasoner-jar",
            str(prompt05_case["jar"]),
            "--json",
        ],
        capsys,
    )
    archive = Path(workspace) / exported["result"]["archive_path"]
    assert archive.is_file()
    archive_report = _run(["verify-archive", str(archive), "--json"], capsys)
    assert archive_report["result"]["package_id"] == package_id
    contents = _run(["contents", str(archive), "--json"], capsys)
    assert "ontology-package.json" in contents["result"]
    assert "ontology-package.lock.json" in contents["result"]


def test_package_archive_error_uses_exit_39_and_json_envelope(tmp_path: Path, capsys) -> None:
    archive = tmp_path / "bad.kgop"
    archive.write_bytes(b"not a zip")
    code = package_main(["verify-archive", str(archive), "--json"])
    envelope = json.loads(capsys.readouterr().out)
    assert code == 39
    assert envelope["errors"][0]["code"] == "PACKAGE_ARCHIVE_INVALID"
