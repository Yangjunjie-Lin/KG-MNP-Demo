"""OWL-RL inference tests."""

from rdflib.namespace import RDF

from kg_mnp_demo.inference import apply_owlrl
from kg_mnp_demo.loader import load_case_graph
from kg_mnp_demo.namespaces import MNP


def test_system_observation_infers_evidence_record():
    g = load_case_graph("CASE-01")
    apply_owlrl(g)
    assert (MNP["Ev-01-ID"], RDF.type, MNP.SystemObservation) in g
    assert (MNP["Ev-01-ID"], RDF.type, MNP.EvidenceRecord) in g


def test_inference_is_deterministic():
    g1 = load_case_graph("CASE-02")
    g2 = load_case_graph("CASE-02")
    apply_owlrl(g1)
    apply_owlrl(g2)

    def grounded(g):
        return {
            (s, p, o)
            for s, p, o in g
            if s.__class__.__name__ != "BNode"
            and p.__class__.__name__ != "BNode"
            and o.__class__.__name__ != "BNode"
        }

    assert grounded(g1) == grounded(g2)
    assert (MNP["Ev-02-ID"], RDF.type, MNP.EvidenceRecord) in g1
    assert (MNP["Ev-02-ID"], RDF.type, MNP.EvidenceRecord) in g2
