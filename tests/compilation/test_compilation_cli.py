import json

from kg_mnp_demo.modeling.cli import main
from ._helpers import ROOT


def test_compile_help_and_build_validate_inspect(tmp_path, capsys):
    output = tmp_path / "full"
    args = [
        "compile", "build",
        "--input", str(ROOT / "examples/modeling/inputs/partial-basic.json"),
        "--proposal", str(ROOT / "examples/modeling/expected-proposals/partial-basic.proposal.json"),
        "--decision-log", str(ROOT / "examples/review/expected-logs/full-confirmation.log.json"),
        "--package", str(ROOT / "examples/review/expected-packages/full-confirmation.package.json"),
        "--output-dir", str(output),
    ]
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["release_status"] == "FORMALLY_VALIDATED"
    assert main([
        "compile", "validate", "--input", str(ROOT / "examples/modeling/inputs/partial-basic.json"),
        "--proposal", str(ROOT / "examples/modeling/expected-proposals/partial-basic.proposal.json"),
        "--decision-log", str(ROOT / "examples/review/expected-logs/full-confirmation.log.json"),
        "--package", str(ROOT / "examples/review/expected-packages/full-confirmation.package.json"),
        "--compilation-dir", str(output),
    ]) == 0
    assert main(["compile", "inspect", "--compilation-dir", str(output)]) == 0
