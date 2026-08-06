from kg_mnp_demo.compilation.rdf_canonical import canonical_nquads
from rdflib import URIRef, Literal


def test_nquads_sort_by_graph_then_terms():
    values = [(URIRef("urn:s"), URIRef("urn:p"), Literal("v"), URIRef("urn:g"))]
    output = canonical_nquads(values)
    assert output == b'<urn:s> <urn:p> "v" <urn:g> .\n'
