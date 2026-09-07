"""Product modeling CLI guarantees; obsolete local-authority cases are in the migration ledger."""
import pytest

from kg_mnp.root_cli import main


def test_model_provider_list_and_conformance(capsys):
    assert main(["model","provider","list","--json"])==0
    output=capsys.readouterr().out
    assert "baseline-reuse-provider" in output and "PROPOSAL_ONLY" in output
    assert main(["model","provider","conformance","rule-mapping-provider","--json"])==0

def test_model_help_exposes_product_commands(capsys):
    with pytest.raises(SystemExit) as raised:
        main(["model","--help"])
    assert raised.value.code==0
    output=capsys.readouterr().out
    for command in ("scope","approve-scope","prepare","propose"):
        assert command in output
    assert "auto-approve" not in output and "--reviewer-role" not in output
