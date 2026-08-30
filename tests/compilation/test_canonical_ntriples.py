from rdflib import Literal, URIRef

from kg_mnp.compilation.rdf_canonical import canonical_ntriples


def test_ntriples_are_sorted_and_lf_terminated():
    triples = [(URIRef("urn:z"), URIRef("urn:p"), Literal("quote\\nline")), (URIRef("urn:a"), URIRef("urn:p"), Literal("a"))]
    output = canonical_ntriples(triples)
    assert output.endswith(b"\n") and b"\r" not in output
    assert output.splitlines() == sorted(output.splitlines())
