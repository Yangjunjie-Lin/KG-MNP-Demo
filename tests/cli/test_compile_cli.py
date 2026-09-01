from __future__ import annotations

import json
from pathlib import Path

from kg_mnp.semantic_kernel.cli import compile_main

ROOT = Path(__file__).resolve().parents[2]


def _options(prompt05_case: dict) -> list[str]:
    return [
        "--domain-packs-root",
        str(ROOT / "domain_packs"),
        "--reasoner-jar",
        str(prompt05_case["jar"]),
        "--json",
    ]


def _run(arguments: list[str], capsys) -> dict:
    assert compile_main(arguments) == 0
    return json.loads(capsys.readouterr().out)


def test_compile_input_plan_build_inspect_validate_reports_and_reproduce_cli(prompt05_case: dict, capsys) -> None:
    workspace = str(prompt05_case["workspace"])
    package_id = prompt05_case["prompt04"]["package"]["package_id"]
    plan_id = prompt05_case["plan"]["plan_id"]
    build_id = prompt05_case["result"].build_id
    input_result = _run(["input", "verify", workspace, "--confirmed", package_id, *_options(prompt05_case)], capsys)
    assert input_result["result"]["status"] == "VALID"
    inspected = _run(["plan", "inspect", workspace, plan_id, "--json"], capsys)
    assert inspected["result"]["plan_id"] == plan_id
    validated = _run(["plan", "validate", workspace, plan_id, "--json"], capsys)
    assert validated["result"]["status"] == "VALID"
    built = _run(["build", workspace, "--plan", plan_id, *_options(prompt05_case)], capsys)
    assert built["result"]["package_id"] == prompt05_case["result"].package_id
    run = _run(["inspect", workspace, build_id, "--json"], capsys)
    assert run["result"]["status"] == "SUCCEEDED"
    checked = _run(["validate", workspace, build_id, "--json"], capsys)
    assert checked["result"]["status"] == "VALID"
    reports = _run(["reports", workspace, build_id, "--json"], capsys)
    assert reports["result"] == ["build-reproduction-report.json", "ontology-package-validation-report.json"]
    reproduction = _run(["reproduce", workspace, build_id, *_options(prompt05_case)], capsys)
    assert reproduction["result"]["status"] == "PASSED"
    assert reproduction["result"]["mismatches"] == []


def test_compile_cli_has_stable_json_error_envelope_without_traceback(capsys, tmp_path: Path) -> None:
    code = compile_main(["input", "verify", str(tmp_path), "--confirmed", "invalid", "--json"])
    output = capsys.readouterr()
    envelope = json.loads(output.out)
    assert code == 28
    assert envelope["status"] == "ERROR" and envelope["code"] == 28
    assert "Traceback" not in output.out and "Traceback" not in output.err
