from __future__ import annotations

from pathlib import Path

from kg_mnp_demo.modeling.cli import main

from ._helpers import ROOT, load_expected_log


def test_confirm_build_and_package_validate(tmp_path: Path, monkeypatch):
    # Ensure the CLI uses the golden final log path under tmp via copy.
    import json

    log_path = tmp_path / "final.json"
    log_path.write_text(
        json.dumps(load_expected_log("full-confirmation"), ensure_ascii=False),
        encoding="utf-8",
    )
    package_path = tmp_path / "package.json"
    assert (
        main(
            [
                "confirm",
                "build",
                "--input",
                str(ROOT / "examples/modeling/inputs/partial-basic.json"),
                "--proposal",
                str(ROOT / "examples/modeling/expected-proposals/partial-basic.proposal.json"),
                "--decision-log",
                str(log_path),
                "--output",
                str(package_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "package",
                "validate",
                "--input",
                str(ROOT / "examples/modeling/inputs/partial-basic.json"),
                "--proposal",
                str(ROOT / "examples/modeling/expected-proposals/partial-basic.proposal.json"),
                "--decision-log",
                str(log_path),
                "--package",
                str(package_path),
            ]
        )
        == 0
    )
    assert main(["package", "inspect", "--package", str(package_path)]) == 0
