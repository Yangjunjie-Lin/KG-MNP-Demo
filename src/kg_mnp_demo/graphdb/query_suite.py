from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from rdflib import RDF

from ..compilation.abox_compiler import FORBIDDEN_PREDICATES, FORBIDDEN_TYPE_OBJECTS
from ..compilation.rdf_canonical import canonical_rdf_term
from ..modeling.canonical_json import canonical_json_bytes

PREFIXES = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX mnp: <https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#>
"""


def _query(value: str) -> str:
    return PREFIXES + value.strip() + "\n"


def _forbidden_business_filter() -> str:
    predicates = ", ".join(
        canonical_rdf_term(term) for term in sorted(FORBIDDEN_PREDICATES, key=str)
    )
    type_objects = ", ".join(
        canonical_rdf_term(term) for term in sorted(FORBIDDEN_TYPE_OBJECTS, key=str)
    )
    return (
        f"?p IN ({predicates}) || "
        f"(?p = {canonical_rdf_term(RDF.type)} && ?o IN ({type_objects}))"
    )


def _forbidden_assertion_query(business: str, triples: Sequence[tuple[Any, Any, Any]]) -> str:
    if not triples:
        return _query(
            f"SELECT ?s ?p ?o WHERE {{ GRAPH <{business}> {{ ?s ?p ?o }} "
            "FILTER(false) } ORDER BY ?s ?p ?o"
        )
    rows = "\n    ".join(
        "("
        + " ".join(canonical_rdf_term(term) for term in triple)
        + ")"
        for triple in sorted(
            set(triples), key=lambda item: tuple(canonical_rdf_term(term) for term in item)
        )
    )
    return _query(
        "SELECT ?s ?p ?o WHERE {\n"
        f"  VALUES (?s ?p ?o) {{\n    {rows}\n  }}\n"
        f"  GRAPH <{business}> {{ ?s ?p ?o }}\n"
        "} ORDER BY ?s ?p ?o"
    )


def build_query_suite(
    named_graphs: Mapping[str, str],
    *,
    tbox_modules: int,
    expected_counts: Mapping[str, int],
    stage06_graphs: Mapping[str, str],
    forbidden_triples: Sequence[tuple[Any, Any, Any]] = (),
    expected_tbox_versions: Sequence[Mapping[str, str]] = (),
    expected_review_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    business = stage06_graphs["business_abox"]
    provenance = stage06_graphs["modeling_provenance"]
    review = stage06_graphs["review_audit"]
    leakage_filter = _forbidden_business_filter()
    review_constraints = ""
    if expected_review_audit:
        log_iri = str(expected_review_audit["decision_log_id"])
        session_iri = str(expected_review_audit["review_session_id"])
        reviewer_iri = str(expected_review_audit["reviewer_id"])
        decision_iris = [
            str(item["decision_id"]) for item in expected_review_audit["decisions"]
        ]
        decision_values = ", ".join(f"<{value}>" for value in decision_iris)
        review_constraints = (
            f"FILTER(?log = <{log_iri}> && ?session = <{session_iri}> "
            f"&& ?reviewer = <{reviewer_iri}> && ?decision IN ({decision_values})) "
            f"FILTER NOT EXISTS {{ GRAPH <{review}> {{ ?extraLog a prov:Entity . "
            f"FILTER(?extraLog != <{log_iri}>) }} }} "
            f"FILTER NOT EXISTS {{ GRAPH <{review}> {{ ?extraSession a prov:Activity . "
            f"FILTER(?extraSession != <{session_iri}>) }} }} "
            f"FILTER NOT EXISTS {{ GRAPH <{review}> {{ ?extraReviewer a prov:Agent . "
            f"FILTER(?extraReviewer != <{reviewer_iri}>) }} }} "
            f"FILTER NOT EXISTS {{ GRAPH <{review}> {{ ?extraDecision a mnp:ReviewDecision . "
            f"FILTER(?extraDecision NOT IN ({decision_values})) }} }} "
        )
    queries = {
        "01-repository-summary": _query(
            "SELECT (COUNT(DISTINCT ?g) AS ?namedGraphCount) "
            "(COUNT(*) AS ?quadCount) (COUNT(DISTINCT ?s) AS ?subjectCount) "
            "(COUNT(DISTINCT ?p) AS ?predicateCount) "
            "(COUNT(DISTINCT ?o) AS ?objectCount) "
            "WHERE { GRAPH ?g { ?s ?p ?o } }"
        ),
        "02-named-graph-counts": _query(
            "SELECT ?g (COUNT(*) AS ?count) WHERE { GRAPH ?g { ?s ?p ?o } } "
            "GROUP BY ?g ORDER BY ?g"
        ),
        "03-business-assertions": _query(
            f"SELECT ?s ?p ?o WHERE {{ GRAPH <{business}> {{ ?s ?p ?o . "
            f"FILTER({leakage_filter}) }} }} ORDER BY ?s ?p ?o"
        ),
        "04-provenance-coverage": _query(
            f"SELECT ?s ?p ?o WHERE {{ GRAPH <{business}> {{ ?s ?p ?o . "
            "FILTER(!(?p = rdf:type && ?o = owl:Ontology) && ?p != owl:imports) "
            f"FILTER NOT EXISTS {{ GRAPH <{provenance}> {{ ?assertion a owl:Axiom ; "
            "owl:annotatedSource ?s ; owl:annotatedProperty ?p ; "
            "owl:annotatedTarget ?o ; mnp:hasReviewDecision ?decision } } } } "
            "ORDER BY ?s ?p ?o"
        ),
        "05-review-audit-coverage": _query(
            f"SELECT ?log ?session ?reviewer ?decision ?outcome ?decidedAt ?subject "
            f"WHERE {{ GRAPH <{review}> {{ "
            "?log a prov:Entity ; prov:wasGeneratedBy ?session ; dcterms:hasPart ?decision . "
            "?session a prov:Activity ; prov:wasAssociatedWith ?reviewer . "
            "?reviewer a prov:Agent . "
            "?decision a mnp:ReviewDecision ; mnp:reviewOutcomeCode ?outcome ; "
            "prov:generatedAtTime ?decidedAt ; dcterms:subject ?subject . "
            f"{review_constraints} }} }} ORDER BY ?decision"
        ),
        "06-tbox-version": _query(
            "SELECT ?g ?ontology ?version WHERE { GRAPH ?g { "
            "?ontology a owl:Ontology ; owl:versionIRI ?version } } "
            "ORDER BY ?g ?ontology ?version"
        ),
        "08-no-tbox-in-business-graph": _query(
            f"ASK {{ FILTER NOT EXISTS {{ GRAPH <{business}> {{ ?s ?p ?o . "
            f"FILTER({leakage_filter}) }} }} }}"
        ),
        "09-no-rejected-business-facts": _forbidden_assertion_query(
            business, forbidden_triples
        ),
        "10-no-blank-nodes": _query(
            "ASK { FILTER NOT EXISTS { GRAPH ?g { ?s ?p ?o . "
            "FILTER(isBlank(?s) || isBlank(?p) || isBlank(?o) || isBlank(?g)) } } }"
        ),
    }
    verifications = {
        query_id: {
            "verification_type": (
                "SPARQL_ASK" if query_id in {
                    "08-no-tbox-in-business-graph", "10-no-blank-nodes"
                } else "SPARQL_SELECT"
            ),
            "query_id": query_id,
        }
        for query_id in queries
    }
    verifications["07-default-graph-storage"] = {
        "verification_type": "GRAPH_STORE_DEFAULT_GRAPH",
        "expected_statement_count": 0,
    }
    normalized_expected = {key: int(value) for key, value in expected_counts.items()}
    content = {
        "contract_version": "1.0",
        "queries": queries,
        "verifications": verifications,
        "expected": {
            "named_graphs": sorted({*named_graphs.values(), *stage06_graphs.values()}),
            "counts": normalized_expected,
            "tbox_module_count": tbox_modules,
            "tbox_versions": [dict(item) for item in expected_tbox_versions],
            "review_audit": dict(expected_review_audit or {}),
            "forbidden_assertion_count": len(set(forbidden_triples)),
            "ask": {
                "08-no-tbox-in-business-graph": True,
                "10-no-blank-nodes": True,
            },
        },
    }
    content["normalization_policy"] = {
        "encoding": "UTF-8",
        "line_endings": "LF",
        "variables": "query declaration order",
        "rows": "RDF-term lexical order",
        "ask": "{boolean: bool}",
    }
    content["query_suite_hash"] = query_suite_hash(content)
    content["query_suite_id"] = (
        f"urn:kg-mnp:graphdb-query-suite:{content['query_suite_hash']}"
    )
    return content


def query_suite_hash(suite: Mapping[str, Any]) -> str:
    queries = suite["queries"]
    query_bytes = b"".join(
        (name + "\n" + str(queries[name])).encode("utf-8")
        for name in sorted(queries)
    )
    return hashlib.sha256(
        query_bytes
        + canonical_json_bytes(suite["verifications"])
        + canonical_json_bytes(suite["expected"])
        + canonical_json_bytes(suite["normalization_policy"])
    ).hexdigest()
