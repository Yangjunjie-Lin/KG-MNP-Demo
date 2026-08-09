from __future__ import annotations

import pytest

from kg_mnp_demo.application.errors import ApplicationError
from kg_mnp_demo.application.identifiers import parse_rdf_term, validate_iri
from kg_mnp_demo.application.query_validator import (
    validate_bound_graph_values,
    validate_query_text,
)


@pytest.mark.parametrize("token", ["INSERT", "DELETE", "CLEAR", "DROP", "CREATE", "LOAD", "MOVE", "COPY", "ADD", "SERVICE", "WITH", "USING"])
def test_sparql_mutation_and_service_tokens_fail_closed(token):
    query = f"SELECT ?s WHERE {{ GRAPH ?g {{ ?s ?p ?o }} }} {token}"
    with pytest.raises(ApplicationError):
        validate_query_text(query, allowed_types=("SELECT",), graph_variables=("g",))


@pytest.mark.parametrize(
    "iri",
    [
        "file:///etc/passwd", "javascript:alert(1)", "https://user:pass@example.com/x",
        "https://evil.example/x", "urn:other:resource", "https://yangjunjie-lin.github.io/KG-MNP-Demo/x\nINSERT DATA {}",
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/" + "x" * 2050,
    ],
)
def test_iri_attacks_fail_closed(iri):
    with pytest.raises(ApplicationError):
        validate_iri(iri)


def test_literal_injection_is_serialized_as_a_literal():
    term = parse_rdf_term({"term_type": "LITERAL", "value": '\" ) } SERVICE <https://evil.example> { ?s ?p ?o } #', "datatype_iri": "http://www.w3.org/2001/XMLSchema#string", "language": None})
    serialized = term.as_rdflib().n3()
    assert serialized.startswith('"')
    assert "\\\"" in serialized


def test_unknown_named_graph_access_fails_even_after_registry_rehash():
    query = "SELECT ?s WHERE { VALUES ?g { <urn:kg-mnp:graph:abox:allowed> <urn:kg-mnp:graph:temporary:evil> } GRAPH ?g { ?s ?p ?o } }"
    with pytest.raises(ApplicationError):
        validate_bound_graph_values(
            query,
            {"g": ("urn:kg-mnp:graph:abox:allowed",)},
        )
