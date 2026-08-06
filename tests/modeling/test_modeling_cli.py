from __future__ import annotations

import json

from kg_mnp_demo.modeling.cli import main

from ._helpers import ROOT


def test_central_cli_lists_closed_contract_catalog(capsys) -> None:
    assert main(["contracts", "list"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert len(output["contracts"]) == 11
    assert output["resolution"] == "OFFLINE_ONLY"


def test_cli_validates_input_and_dependencies(capsys) -> None:
    input_path = ROOT / "examples" / "modeling" / "inputs" / "partial-basic.json"
    assert main([
        "contracts",
        "validate",
        "--contract",
        "cleaned-partial-data",
        "--input",
        str(input_path),
    ]) == 0
    capsys.readouterr()
    assert main(["dependencies", "verify"]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True


def test_cli_proposal_output_is_byte_stable_and_not_overwritten(tmp_path, capsys) -> None:
    input_path = ROOT / "examples" / "modeling" / "inputs" / "partial-basic.json"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    for output in (first, second):
        assert main(["propose", "--input", str(input_path), "--output", str(output)]) == 0
        capsys.readouterr()
    assert first.read_bytes() == second.read_bytes()
    assert main(["propose", "--input", str(input_path), "--output", str(first)]) == 1
    assert "--force" in capsys.readouterr().err
    assert main(["proposal", "validate", "--input", str(first)]) == 0

