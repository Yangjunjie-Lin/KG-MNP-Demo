"""Tests for AssessmentService and stable output contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from kg_mnp_demo.application.assessment_service import AssessmentService
from kg_mnp_demo.application.contracts import ASSESSMENT_RESPONSE_KEYS, SCHEMA_VERSION
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.cli import cmd_evaluate_rdf
from kg_mnp_demo.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def case03_payload() -> dict:
    return json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))


@pytest.fixture
def service() -> AssessmentService:
    return AssessmentService()


def _strip_volatile(result: dict) -> dict:
    data = copy.deepcopy(result)
    data.pop("execution_id", None)
    data.pop("artifacts", None)
    return data


def test_assess_dict_full_run(service, case03_payload):
    result = service.assess_dict(case03_payload)
    assert "error" not in result
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["case_id"] == "CASE-03"
    assert result["decision"] == "BLOCKED"
    assert result["publication"]["publishable"] is True
    assert result["blocking_reasons"][0]["reason_code"] == "ACTIVE_CONTRACT_RESTRICTION"
    for key in ASSESSMENT_RESPONSE_KEYS:
        assert key in result


def test_assess_file_full_run(service, tmp_path):
    result = service.assess_file(
        ROOT / "inputs" / "case03.json",
        persist_artifacts=True,
        artifact_dir=tmp_path / "out",
    )
    assert result["decision"] == "BLOCKED"
    assert (tmp_path / "out" / "assessment_response.json").exists()
    assert result["artifacts"]["evaluation"] == "evaluation.json"


def test_result_json_dumps(service, case03_payload):
    result = service.assess_dict(case03_payload)
    encoded = json.dumps(result, ensure_ascii=False)
    assert "CASE-03" in encoded
    # No absolute Windows/Unix paths
    assert ":\\\\" not in encoded
    assert "/Users/" not in encoded
    assert "D:\\\\" not in encoded.upper() or "D:\\\\" not in encoded


def test_repeatable_except_execution_id(service, case03_payload):
    a = service.assess_dict(case03_payload)
    b = service.assess_dict(case03_payload)
    assert a["execution_id"] != b["execution_id"]
    assert _strip_volatile(a) == _strip_volatile(b)


def test_invalid_json_schema_error(service):
    result = service.assess_dict({"case_id": "X"})
    assert "error" in result
    assert result["error"]["code"] == ErrorCode.INPUT_SCHEMA_ERROR.value
    assert result["error"]["retryable"] is False


def test_invalid_json_file(service, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    result = service.assess_file(bad)
    assert result["error"]["code"] == ErrorCode.INPUT_SCHEMA_ERROR.value


def test_case03_unchanged(service, case03_payload):
    result = service.assess_dict(case03_payload)
    assert result["decision"] == "BLOCKED"
    reasons = result["blocking_reasons"]
    assert len(reasons) == 1
    assert reasons[0]["rule_id"] == "MNP-ELIG-004"
    assert reasons[0]["rule_version"] == "1.0"
    assert reasons[0]["regulatory_clause"] == "REG-MNP-CLAUSE-04"
    assert reasons[0]["action_code"] == "WAIT_OR_TERMINATE_CONTRACT"


def test_what_if_contract_expired_becomes_eligible(service, case03_payload):
    changes = {
        "assessment_time": "2027-01-02T00:00:00Z",
        "evidence": {
            "identity": {"valid_until": "2027-12-31T23:59:59Z"},
            "number_status": {"valid_until": "2027-12-31T23:59:59Z"},
            "billing": {"valid_until": "2027-12-31T23:59:59Z"},
            "contract": {
                "contract_status": "EXPIRED",
                "contract_end_time": "2027-01-01T00:00:00Z",
                "valid_until": "2027-12-31T23:59:59Z",
            },
            "porting_history": {"valid_until": "2027-12-31T23:59:59Z"},
        },
    }
    result = service.run_what_if(case03_payload, changes)
    assert result["baseline"]["decision"] == "BLOCKED"
    assert result["scenario"]["decision"] == "ELIGIBLE"
    assert result["decision_changed"] is True


def test_cli_and_service_agree(service, case03_payload, tmp_path):
    service_result = service.assess_dict(case03_payload)
    pipeline_result = run_pipeline(
        ROOT / "inputs" / "case03.json",
        tmp_path / "pipe",
        write_html=False,
    )
    assert pipeline_result["decision"] == service_result["decision"]
    assert (
        pipeline_result["evaluation"]["blocking_reasons"][0]["reason_code"]
        == service_result["blocking_reasons"][0]["reason_code"]
    )


def test_cli_rdf_case03_blocked(capsys):
    code = cmd_evaluate_rdf("CASE-03")
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "BLOCKED"


def test_application_error_structure():
    err = ApplicationError(ErrorCode.INPUT_GRAPH_INVALID, details=["x"])
    payload = err.to_dict()
    assert payload == {
        "error": {
            "code": "INPUT_GRAPH_INVALID",
            "message": "输入图未通过 SHACL 验证。",
            "details": ["x"],
            "retryable": False,
        }
    }
