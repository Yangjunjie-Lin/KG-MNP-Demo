"""Runtime regressions for the legacy eligibility JSON input contract."""

from __future__ import annotations

import copy
import io
import json
from pathlib import Path

import pytest

from kg_mnp_demo import cli
from kg_mnp_demo.cli import main
from kg_mnp_demo.input_adapter import (
    InputValidationError,
    load_and_normalize,
    normalize_case_input,
)


ROOT = Path(__file__).resolve().parents[2]
VALID_INPUT = ROOT / "inputs" / "case03.json"


def _valid_payload() -> dict[str, object]:
    return json.loads(VALID_INPUT.read_text(encoding="utf-8"))


def test_legacy_adapter_accepts_valid_input_through_both_entry_points() -> None:
    direct = normalize_case_input(_valid_payload())
    loaded = load_and_normalize(VALID_INPUT)

    assert direct == loaded
    assert loaded.case_id == "CASE-03"
    assert loaded.contract.contract_status == "ACTIVE"


def test_load_and_normalize_rejects_missing_evidence_source() -> None:
    with pytest.raises(InputValidationError, match="source_system"):
        load_and_normalize(ROOT / "inputs" / "invalid_missing_source.json")


def test_normalize_rejects_invalid_datetime() -> None:
    payload = copy.deepcopy(_valid_payload())
    payload["evidence"]["contract"]["contract_end_time"] = "not-a-date"  # type: ignore[index]

    with pytest.raises(InputValidationError, match="date-time"):
        normalize_case_input(payload)


def test_normalize_rejects_unexpected_contract_field() -> None:
    payload = copy.deepcopy(_valid_payload())
    payload["unexpected_future_modeling_contract"] = {}  # type: ignore[index]

    with pytest.raises(InputValidationError, match="Additional properties"):
        normalize_case_input(payload)


@pytest.mark.parametrize("command", ["evaluate", "trace"])
def test_legacy_cli_commands_continue_to_work(command: str, capsys) -> None:
    assert main([command, "--case", "CASE-03", "--backend", "rdf"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["case_id"] == "CASE-03"
    assert payload["backend"] == "rdf"
    assert "decision" in payload if command == "evaluate" else "decision_trace" in payload


def test_legacy_cli_json_is_safe_on_non_utf8_stdout(monkeypatch) -> None:
    class AsciiStream(io.StringIO):
        encoding = "ascii"

    stream = AsciiStream()
    monkeypatch.setattr(cli.sys, "stdout", stream)

    cli._json_print({"label": "资格判断"})

    rendered = stream.getvalue()
    assert "\\u" in rendered
    assert json.loads(rendered) == {"label": "资格判断"}
