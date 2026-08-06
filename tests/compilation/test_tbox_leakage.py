import copy
import pytest
from rdflib import OWL, RDF, RDFS, SH, Graph

from kg_mnp_demo.compilation.abox_compiler import ABoxCompilationError, compile_abox
from ._helpers import ROOT, authorities


FORBIDDEN_PREDICATES = {
    RDFS.subClassOf,
    RDFS.subPropertyOf,
    RDFS.domain,
    RDFS.range,
    OWL.equivalentClass,
    OWL.equivalentProperty,
    OWL.disjointWith,
}
FORBIDDEN_TYPE_OBJECTS = {
    OWL.Class,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    SH.NodeShape,
    SH.PropertyShape,
}


def test_tbox_term_type_is_rejected():
    values = list(authorities())
    proposal = copy.deepcopy(values[1])
    candidate = proposal["candidate_entities"][0]
    candidate["class_iri"] = "http://www.w3.org/2002/07/owl#Class"
    with pytest.raises((ABoxCompilationError, ValueError)):
        compile_abox(values[3], proposal, values[4])


def test_tbox_publication_scope_is_rejected():
    values = list(authorities())
    package = copy.deepcopy(values[3])
    package["confirmed_abox_decisions"][0]["publication_scope"] = "TBOX"
    with pytest.raises(ABoxCompilationError, match="ABOX publication scope"):
        compile_abox(package, values[1], values[4])


@pytest.mark.parametrize("scenario", [
    "full-confirmation",
    "modified-confirmation",
    "rejection",
    "issue-resolution",
])
def test_tbox_leakage_is_absent_from_parsed_golden_abox(scenario):
    root = ROOT / "examples" / "compilation" / "expected" / scenario / "rdf"
    for filename, rdf_format in (("abox.nt", "nt"), ("abox.ttl", "turtle")):
        graph = Graph()
        graph.parse(root / filename, format=rdf_format)
        for _, predicate, obj in graph:
            assert predicate not in FORBIDDEN_PREDICATES
            assert not (predicate == RDF.type and obj in FORBIDDEN_TYPE_OBJECTS)
