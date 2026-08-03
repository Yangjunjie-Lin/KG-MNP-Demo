"""OntologyService API tests."""

from __future__ import annotations

import json

from kg_mnp_demo.application.ontology_service import OntologyService


def test_summary_and_modules():
    svc = OntologyService()
    summary = svc.get_summary()
    assert summary["class_count"] > 20
    assert summary["object_property_count"] > 10
    modules = svc.list_modules()
    codes = {m["module"] for m in modules}
    assert "IDENTITY" in codes
    assert "PROCESS" in codes
    assert "COMPLIANCE" in codes
    identity = next(m for m in modules if m["module"] == "IDENTITY")
    assert identity["label_zh"] == "用户与身份层"
    assert "NaturalPerson" in identity["classes"]


def test_class_and_property_detail():
    svc = OntologyService()
    detail = svc.get_class_detail("EligibilityAssessment")
    assert detail is not None
    assert detail["local_name"] == "EligibilityAssessment"
    prop = svc.get_property_detail("usesEvidence")
    assert prop is not None
    assert "EligibilityAssessment" in prop["domain"]


def test_graph_json_serializable():
    svc = OntologyService()
    graph = svc.build_ontology_graph(module="IDENTITY")
    json.dumps(graph)
    assert all(n["module"] == "IDENTITY" for n in graph["nodes"])
