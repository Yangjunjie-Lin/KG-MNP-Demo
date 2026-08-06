from rdflib import BNode, Graph

from ._helpers import build


def test_formal_rdf_artifacts_have_no_blank_nodes(tmp_path):
    directory, _, _ = build(tmp_path)
    for relative, fmt in (("rdf/abox.nt", "nt"), ("rdf/modeling-provenance.nt", "nt"), ("rdf/review-audit.nt", "nt"), ("rdf/dataset.nq", "nquads"), ("shacl/report.nt", "nt")):
        graph = Graph()
        graph.parse(directory / relative, format=fmt)
        assert all(not isinstance(term, BNode) for triple in graph for term in triple)
