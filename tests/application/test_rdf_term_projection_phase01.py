from __future__ import annotations

from kg_mnp_demo.application.result_normalizer import normalize_binding


def test_rdf_term_projection_preserves_iri_datatype_language_and_lexical_form():
    assert normalize_binding({"type": "uri", "value": "urn:kg-mnp:x"}) == {"term_type": "IRI", "iri": "urn:kg-mnp:x"}
    assert normalize_binding({"type": "literal", "value": "2026-08-09", "datatype": "http://www.w3.org/2001/XMLSchema#date"}) == {"term_type": "LITERAL", "lexical_form": "2026-08-09", "datatype_iri": "http://www.w3.org/2001/XMLSchema#date", "language": None}
    assert normalize_binding({"type": "literal", "value": "名称", "xml:lang": "zh"}) == {"term_type": "LITERAL", "lexical_form": "名称", "datatype_iri": None, "language": "zh"}
