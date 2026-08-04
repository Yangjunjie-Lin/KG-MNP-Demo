from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from kg_mnp_demo.api.app import create_app
from kg_mnp_demo.api.dependencies import AppState
from kg_mnp_demo.storage import AssessmentRepository, ArtifactRepository, Database

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(tmp_path):
    db = Database(tmp_path / "api.sqlite3")
    state = AppState(
        db=db,
        repository=AssessmentRepository(db),
        artifacts=ArtifactRepository(tmp_path / "executions"),
    )
    with TestClient(create_app(state)) as c:
        yield c, state, tmp_path


def _case(name="case03.json"):
    return json.loads((ROOT / "inputs" / name).read_text(encoding="utf-8"))


def test_health_ready_meta_openapi(client):
    c, _, _ = client
    assert c.get("/api/v1/health").status_code == 200
    assert c.get("/api/v1/ready").json()["status"] == "ready"
    assert c.get("/api/v1/meta").status_code == 200
    empty_latest = c.get("/api/v1/cases/CASE-03/latest")
    assert empty_latest.status_code == 200
    assert empty_latest.json() is None
    openapi = c.get("/openapi.json").json()
    assert "/api/v1/assessments" in openapi["paths"]
    assert "/api/v1/views/cases" in openapi["paths"]
    schema = openapi["components"]["schemas"]
    assert "MNPCaseInput" in schema or "AssessmentCreateRequest" in schema
    # payload must not be empty free-form only
    create = schema.get("AssessmentCreateRequest") or {}
    props = create.get("properties") or {}
    assert "payload" in props
    payload_ref = json.dumps(props["payload"])
    assert "AdditionalProperties" not in payload_ref or "MNPCaseInput" in json.dumps(schema)


def test_post_case03_and_history(client):
    c, state, tmp = client
    resp = c.post("/api/v1/assessments", json={"payload": _case(), "persist": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "BLOCKED"
    eid = data["execution_id"]
    assert c.get(f"/api/v1/assessments/{eid}").status_code == 200
    assert "nodes" in c.get(f"/api/v1/assessments/{eid}/trace").json()
    assert c.get(f"/api/v1/assessments/{eid}/artifacts").status_code == 200
    assert c.get("/api/v1/cases/CASE-03/history").status_code == 200
    assert c.get("/api/v1/cases/CASE-03/latest").status_code == 200
    # idempotent: no second artifact dir
    dirs_before = list((tmp / "executions").iterdir()) if (tmp / "executions").exists() else []
    resp2 = c.post("/api/v1/assessments", json={"payload": _case(), "persist": True})
    assert resp2.json()["execution_id"] == eid
    dirs_after = list((tmp / "executions").iterdir())
    assert len(dirs_after) == len(dirs_before)


def test_invalid_input_unified_error(client):
    c, _, _ = client
    resp = c.post("/api/v1/assessments", json={"payload": {"case_id": "X"}, "persist": False})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INPUT_SCHEMA_ERROR"
    assert "Traceback" not in resp.text


def test_ontology_cq_rules_views(client):
    c, _, _ = client
    assert c.get("/api/v1/ontology/summary").status_code == 200
    assert c.get("/api/v1/ontology/modules").status_code == 200
    assert c.get("/api/v1/ontology/classes").status_code == 200
    assert c.get("/api/v1/ontology/classes/EligibilityAssessment").status_code == 200
    assert c.get("/api/v1/ontology/properties").status_code == 200
    assert c.get("/api/v1/ontology/graph").status_code == 200
    assert c.get("/api/v1/competency-questions").status_code == 200
    assert c.get("/api/v1/competency-questions/CQ-01").status_code == 200
    cq = c.post("/api/v1/competency-questions/CQ-02/execute", json={"case_id": "CASE-04"})
    assert cq.status_code == 200
    assert cq.json()["status"] == "ANSWERED"
    assert len(cq.json()["rows"]) >= 2
    assert c.get("/api/v1/rules").status_code == 200
    assert c.get("/api/v1/rules/MNP-ELIG-005").status_code == 200
    assert c.get("/api/v1/rules/MNP-ELIG-005/versions").status_code == 200
    affected = c.get(
        "/api/v1/rule-updates/affected-assessments",
        params={"rule_id": "MNP-ELIG-005", "old_version": "1.0", "new_version": "1.1"},
    )
    assert affected.status_code == 200
    assert affected.json()["items"] == []
    dash = c.get("/api/v1/views/dashboard").json()
    assert dash["ontology"]["shape_count"] is not None
    assert dash["ontology"]["shape_count"] > 0
    assert "example_cases" in dash and "executions" in dash
    assert c.get("/api/v1/views/ontology").status_code == 200


def test_aggregated_case_view_returns_all_cases_and_latest_by_assessment_time(client):
    c, state, _ = client

    empty = c.get("/api/v1/views/cases")
    assert empty.status_code == 200
    empty_items = {item["case_id"]: item for item in empty.json()["items"]}
    assert set(empty_items) == {f"CASE-{index:02d}" for index in range(1, 10)}
    assert all(item["execution_count"] == 0 for item in empty_items.values())
    assert all(item["has_history"] is False for item in empty_items.values())

    # Insert two records in reverse write order.  The later business
    # assessment timestamp must win even when it was written first.
    def save(case_id: str, execution_id: str, assessment_time: str, decision: str):
        payload = {"case_id": case_id, "assessment_time": assessment_time}
        result = {
            "execution_id": execution_id,
            "case_id": case_id,
            "assessment_time": assessment_time,
            "decision": decision,
            "publication": {"publishable": True, "status": "PUBLISHABLE"},
            "blocking_reasons": [],
        }
        return state.repository.save_execution(
            execution_id=execution_id,
            case_id=case_id,
            assessment_time=assessment_time,
            input_payload=payload,
            result=result,
        )

    save("CASE-06", "case06-latest", "2027-01-01T00:00:00Z", "BLOCKED")
    save("CASE-06", "case06-older", "2026-01-01T00:00:00Z", "BLOCKED")
    save("CASE-01", "case01-only", "2026-05-01T00:00:00Z", "ELIGIBLE")

    response = c.get("/api/v1/views/cases")
    assert response.status_code == 200
    items = {item["case_id"]: item for item in response.json()["items"]}
    case06 = items["CASE-06"]
    assert case06["latest_execution_id"] == "case06-latest"
    assert case06["latest_assessment_time"] == "2027-01-01T00:00:00Z"
    assert case06["latest_decision"] == "BLOCKED"
    assert case06["execution_count"] == 2
    assert case06["has_history"] is True
    assert case06["expected_decision"] == "BLOCKED"
    assert items["CASE-01"]["execution_count"] == 1
    assert items["CASE-02"]["latest_execution_id"] is None


def test_what_if_and_compare(client):
    c, _, _ = client
    created = c.post("/api/v1/assessments", json={"payload": _case(), "persist": True}).json()
    eid = created["execution_id"]
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
    wi = c.post(f"/api/v1/assessments/{eid}/what-if", json={"changes": changes})
    assert wi.status_code == 200
    body = wi.json()
    assert body["decision_change"]["changed"] is True
    assert any(r.get("changed") for r in body["rule_changes"])
    assert "evidence_changes" in body
    # second assessment for compare
    alt = dict(_case())
    alt["assessment_time"] = "2027-01-02T00:00:00Z"
    for k in alt["evidence"]:
        alt["evidence"][k]["valid_until"] = "2027-12-31T23:59:59Z"
    alt["evidence"]["contract"]["contract_status"] = "EXPIRED"
    alt["evidence"]["contract"]["contract_end_time"] = "2027-01-01T00:00:00Z"
    right = c.post("/api/v1/assessments", json={"payload": alt, "persist": True}).json()
    cmp = c.get(
        "/api/v1/assessments/compare",
        params={"left": eid, "right": right["execution_id"]},
    )
    assert cmp.status_code == 200
    assert cmp.json()["decision_changed"] is True
    assert isinstance(cmp.json()["changed_evidence"], dict)


def test_not_found_codes(client):
    c, _, _ = client
    r = c.get("/api/v1/assessments/missing")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "EXECUTION_NOT_FOUND"
    r2 = c.get("/api/v1/ontology/classes/NoSuchClassXYZ")
    assert r2.status_code == 404
    assert r2.json()["error"]["code"] == "ONTOLOGY_TERM_NOT_FOUND"
    r3 = c.get("/api/v1/rules/NO-RULE")
    assert r3.status_code == 404
    assert r3.json()["error"]["code"] == "RULE_NOT_FOUND"
