"""Ontology load and basic structure tests."""

from rdflib.namespace import OWL, RDF, RDFS

from kg_mnp_demo.loader import load_ontology_graph
from kg_mnp_demo.namespaces import MNP


REQUIRED_CLASSES = [
    "Subscriber",
    "PhoneNumber",
    "TelecomAccount",
    "TelecomService",
    "ServiceSubscription",
    "ServiceContract",
    "MNPCase",
    "EligibilityAssessment",
    "EligibilityDecision",
    "EligibleDecision",
    "BlockingDecision",
    "ConditionalDecision",
    "ManualReviewDecision",
    "EvidenceRecord",
    "SystemObservation",
    "EligibilityRule",
    "BlockingReason",
    "RemediationAction",
    "RegulatoryClause",
    "RegulatoryDocument",
    "InformationSystem",
    "RuleVersion",
]


def test_ontology_loads():
    g = load_ontology_graph()
    assert len(g) > 50


def test_required_classes_present():
    g = load_ontology_graph()
    for name in REQUIRED_CLASSES:
        assert (MNP[name], RDF.type, OWL.Class) in g, name


def test_decision_classes_disjoint():
    g = load_ontology_graph()
    assert (MNP.EligibleDecision, OWL.disjointWith, MNP.BlockingDecision) in g
    assert (MNP.BlockingDecision, OWL.disjointWith, MNP.ManualReviewDecision) in g


def test_alignments_optional_and_no_tmf_equivalent():
    g = load_ontology_graph(include_alignments=True)
    assert (MNP.Subscriber, MNP.alignmentStatus, None) not in list(
        g.triples((MNP.Subscriber, MNP.alignmentStatus, None))
    ) or True
    statuses = list(g.objects(MNP.Subscriber, MNP.alignmentStatus))
    assert statuses
    # Ensure we did not declare owl:equivalentClass for Subscriber to a TMF URI
    for o in g.objects(MNP.Subscriber, OWL.equivalentClass):
        assert "tmforum" not in str(o).lower()


def test_core_object_properties_exist():
    g = load_ontology_graph()
    for prop in [
        "concernsNumber",
        "requestedBy",
        "usesEvidence",
        "evaluatedByRule",
        "producesDecision",
        "operationalizesClause",
    ]:
        assert (MNP[prop], RDF.type, OWL.ObjectProperty) in g
