from __future__ import annotations

import json
from pathlib import Path

from kg_mnp_demo.application.assessment_service import AssessmentService
from kg_mnp_demo.application.comparison import compare_evidence
from kg_mnp_demo.presentation import (
    AssessmentView,
    CaseCatalogView,
    ComparisonView,
    DashboardView,
    OntologyView,
)
from kg_mnp_demo.presentation._core import count_shacl_shapes
from kg_mnp_demo.application.ontology_service import OntologyService
from kg_mnp_demo.loader import shapes_path

ROOT = Path(__file__).resolve().parents[2]


def test_shape_count_from_file(tmp_path):
    stats = count_shacl_shapes()
    assert stats["shape_count"] > 0
    assert stats["node_shape_count"] > 0
    # Mutate a copy and ensure count changes
    text = shapes_path().read_text(encoding="utf-8")
    copy = tmp_path / "shapes.ttl"
    copy.write_text(
        text
        + """
@prefix mnp: <http://example.org/kg-mnp#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
mnp:ExtraTestShape a sh:NodeShape ; sh:targetClass mnp:MappingRecord .
""",
        encoding="utf-8",
    )
    mutated = count_shacl_shapes(copy)
    assert mutated["node_shape_count"] == stats["node_shape_count"] + 1


def test_dashboard_stats_split():
    dash = DashboardView().build(ontology=OntologyService(), repository=None)
    assert dash["example_cases"]["total"] == 9
    assert dash["executions"]["total"] == 0
    assert dash["latest_case_states"]["total"] == 0
    assert dash["ontology"]["shape_count"] == count_shacl_shapes()["shape_count"]
    assert "D:\\" not in json.dumps(dash)


def test_case_catalog_view_aggregates_history_and_keeps_empty_cases():
    class FakeRepository:
        calls = 0

        def list_executions(self, *, limit, offset):
            self.calls += 1
            assert limit is None
            assert offset == 0
            # Deliberately return newest write first; latest must follow the
            # business assessment timestamp instead of list/write order.
            return [
                {
                    "execution_id": "case06-old-assessment",
                    "case_id": "CASE-06",
                    "assessment_time": "2026-01-01T00:00:00Z",
                    "created_at": "2026-08-04T00:00:02Z",
                    "decision": "BLOCKED",
                    "publication_status": "PUBLISHABLE",
                },
                {
                    "execution_id": "case06-new-assessment",
                    "case_id": "CASE-06",
                    "assessment_time": "2027-01-01T00:00:00Z",
                    "created_at": "2026-08-04T00:00:01Z",
                    "decision": "BLOCKED",
                    "publication_status": "PUBLISHABLE",
                },
                {
                    "execution_id": "case01-only",
                    "case_id": "CASE-01",
                    "assessment_time": "2026-05-01T00:00:00Z",
                    "created_at": "2026-08-04T00:00:03Z",
                    "decision": "ELIGIBLE",
                    "publication_status": "PUBLISHABLE",
                },
            ]

    repository = FakeRepository()
    body = CaseCatalogView().build(repository)
    assert repository.calls == 1
    assert len(body["items"]) == 9
    items = {item["case_id"]: item for item in body["items"]}
    assert items["CASE-06"]["execution_count"] == 2
    assert items["CASE-06"]["latest_execution_id"] == "case06-new-assessment"
    assert items["CASE-06"]["latest_decision"] == "BLOCKED"
    assert items["CASE-01"]["has_history"] is True
    assert items["CASE-01"]["latest_execution_id"] == "case01-only"
    assert items["CASE-02"]["execution_count"] == 0
    assert items["CASE-02"]["latest_execution_id"] is None


def test_case04_two_reason_cards():
    from kg_mnp_demo.loader import load_case_graph
    from kg_mnp_demo.inference import apply_owlrl
    from kg_mnp_demo.evaluator import evaluate_case
    from kg_mnp_demo.application.contracts import build_assessment_response

    g = load_case_graph("CASE-04")
    apply_owlrl(g)
    ev = evaluate_case(g, "CASE-04", use_updated_rules=True, validate=False)
    fake = build_assessment_response(
        execution_id="x",
        case_id="CASE-04",
        assessment_time=ev["assessment_time"],
        decision=ev["decision"],
        publication={"publishable": True, "status": "PUBLISHABLE"},
        validations={},
        blocking_reasons=ev["blocking_reasons"],
        rule_results=ev["rules"],
        evidence=ev["evidence"],
    )
    view = AssessmentView().build(fake)
    assert len(view["blocking_reason_cards"]) >= 2


def test_case07_eligibility_vs_process():
    payload = json.loads((ROOT / "inputs" / "case07.json").read_text(encoding="utf-8"))
    result = AssessmentService().assess_dict(payload)
    view = AssessmentView().build(result)
    assert view["decision_card"]["decision"] == "ELIGIBLE"
    assert view["process_status"]["can_advance"] is False


def test_what_if_rule_and_evidence_changes():
    payload = json.loads((ROOT / "inputs" / "case03.json").read_text(encoding="utf-8"))
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
    result = AssessmentService().run_what_if(payload, changes)
    view = ComparisonView().build(result)
    assert view["decision_change"]["changed"] is True
    assert any(r.get("changed") for r in view["rule_changes"])
    assert "evidence_changes" in view


def test_ontology_key_paths_real():
    view = OntologyView().build(OntologyService())
    assert view["key_paths"]
    assert all(p["exists_in_rdf"] for p in view["key_paths"])


def test_amount_normalization_not_false_diff():
    a = [{"evidence_id": "E1", "evidence_type": "BILLING_BALANCE", "outstanding_amount": 0}]
    b = [{"evidence_id": "E1", "evidence_type": "BILLING_BALANCE", "outstanding_amount": "0.00"}]
    diff = compare_evidence(a, b)
    assert diff["modified"] == []
