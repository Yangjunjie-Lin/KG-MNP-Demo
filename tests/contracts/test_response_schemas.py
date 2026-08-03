"""Contract schema smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from kg_mnp_demo.application.assessment_service import AssessmentService
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "api"


def _load(name: str):
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_assessment_response_schema():
    schema = _load("AssessmentResponse.json")
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
    result = AssessmentService().assess_dict(payload)
    Draft202012Validator(schema).validate(result)


def test_error_response_schema():
    schema = _load("ErrorResponse.json")
    err = ApplicationError(ErrorCode.INPUT_SCHEMA_ERROR, details=["x"]).to_dict()
    Draft202012Validator(schema).validate(err)
