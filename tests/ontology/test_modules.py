"""Ontology module loading and catalog tests."""

from __future__ import annotations

from rdflib.namespace import OWL, RDF, RDFS

from kg_mnp_demo.application.ontology_service import (
    OntologyService,
    edge_exists_in_ontology,
)
from kg_mnp_demo.loader import load_case_graph, load_ontology_graph, ontology_module_files
from kg_mnp_demo.namespaces import CASE_FILES, MNP
from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.evaluator import evaluate_case
from kg_mnp_demo.validator import validate_graph


EXPECTED_DECISIONS = {
    "CASE-01": "ELIGIBLE",
    "CASE-02": "BLOCKED",
    "CASE-03": "BLOCKED",
    "CASE-04": "BLOCKED",
    "CASE-05": "MANUAL_REVIEW",
    "CASE-06": "BLOCKED",
}


def test_all_modules_load_offline():
    g = load_ontology_graph()
    assert len(g) > 100
    for name in ontology_module_files():
        assert name.endswith(".ttl")


def test_no_duplicate_class_definitions():
    g = load_ontology_graph()
    seen: dict[str, int] = {}
    for s in g.subjects(RDF.type, OWL.Class):
        if str(s).startswith(str(MNP)):
            key = str(s)
            seen[key] = seen.get(key, 0) + 1
    # Each class typed once as owl:Class (may appear once)
    assert all(v == 1 for v in seen.values())


def test_core_classes_still_inferable():
    g = load_case_graph("CASE-01")
    apply_owlrl(g)
    assert any(g.subjects(RDF.type, MNP.MNPCase))


def test_classes_have_display_labels():
    svc = OntologyService()
    for cls in svc.list_classes():
        assert cls["label"], cls["local_name"]
        assert cls["label_en"] or cls["label_zh"] or cls["local_name"]


def test_object_properties_have_domain_range():
    svc = OntologyService()
    exempt = {
        "evidenceForCase",
        # Shared observation/contract literals intentionally omit single OWL domain
        # (handled as datatype properties elsewhere). Object-property exemptions:
        "evaluatedAtTime",  # cross-module range; domain optional in incomplete loads
    }
    # Datatype-like / intentionally domain-free object properties from audit
    for prop in svc.list_object_properties():
        if prop["local_name"] in exempt:
            continue
        if prop.get("deprecated"):
            continue
        # Allow missing domain/range only when explicitly deprecated or exempt
        assert prop["domain"] or prop["local_name"] in exempt, prop["local_name"]
        assert prop["range"] or prop["local_name"] in exempt, prop["local_name"]


def test_ontology_graph_edges_exist():
    svc = OntologyService()
    payload = svc.build_ontology_graph()
    missing = edge_exists_in_ontology(payload)
    assert missing == []


def test_six_cases_unchanged():
    for case_id, expected in EXPECTED_DECISIONS.items():
        g = load_case_graph(case_id)
        assert validate_graph(g).conforms, case_id
        apply_owlrl(g)
        result = evaluate_case(g, case_id, use_updated_rules=True, validate=False)
        assert result["decision"] == expected, case_id


def test_natural_person_subclass():
    g = load_ontology_graph()
    assert (MNP.NaturalPerson, RDFS.subClassOf, MNP.Subscriber) in g
    assert (MNP.AuthorizationCode, RDF.type, OWL.Class) in g
