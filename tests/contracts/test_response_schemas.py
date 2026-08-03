"""Validate all frozen API response JSON Schemas against real payloads."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from kg_mnp_demo.application.assessment_service import AssessmentService
from kg_mnp_demo.application.errors import ApplicationError, ErrorCode
from kg_mnp_demo.application.ontology_service import OntologyService
from kg_mnp_demo.application.query_service import QueryService
from kg_mnp_demo.evaluator import materialize_assessment
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph
from kg_mnp_demo.presentation import ComparisonView, DashboardView

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "api"


def _load(name: str):
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _validate(name: str, payload: dict):
    Draft202012Validator(_load(name)).validate(payload)


def test_all_contract_schemas():
    svc = AssessmentService()
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
    assessment = svc.assess_dict(payload)
    _validate("AssessmentResponse.json", assessment)

    err = ApplicationError(ErrorCode.INPUT_SCHEMA_ERROR, details=["x"]).to_dict()
    _validate("ErrorResponse.json", err)

    graph = OntologyService().build_ontology_graph(module="IDENTITY")
    _validate("OntologyGraphResponse.json", graph)

    _validate("TraceGraphResponse.json", assessment["trace_subgraph"])

    dash = DashboardView().build(ontology=OntologyService(), repository=None)
    # Ensure required keys for frozen schema
    assert "example_cases" in dash
    _validate("DashboardViewResponse.json", dash)

    case_view = {"case": payload, "latest_assessment": None}
    _validate("CaseViewResponse.json", case_view)

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
    what_if = ComparisonView().build(svc.run_what_if(payload, changes))
    _validate("WhatIfResponse.json", what_if)

    g = load_case_graph("CASE-01")
    apply_owlrl(g)
    materialize_assessment(g, "CASE-01", use_updated_rules=True, validate=False)
    cq = QueryService().execute("CQ-01", case_id="CASE-01", graph=g)
    _validate("CompetencyQuestionResponse.json", cq)
