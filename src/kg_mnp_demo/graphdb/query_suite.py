from __future__ import annotations

import hashlib
from typing import Any, Mapping

from ..modeling.canonical_json import canonical_json_bytes

PREFIXES = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX mnp: <https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#>
"""


def _query(value: str) -> str:
    return PREFIXES + value.strip() + "\n"


def build_query_suite(named_graphs: Mapping[str, str], *, tbox_modules: int, expected_counts: Mapping[str, int], stage06_graphs: Mapping[str, str]) -> dict[str, Any]:
    business = stage06_graphs["business_abox"]
    provenance = stage06_graphs["modeling_provenance"]
    review = stage06_graphs["review_audit"]
    queries = {
        "01-repository-summary": _query("SELECT (COUNT(DISTINCT ?g) AS ?namedGraphCount) (COUNT(*) AS ?quadCount) (COUNT(DISTINCT ?s) AS ?subjectCount) (COUNT(DISTINCT ?p) AS ?predicateCount) (COUNT(DISTINCT ?o) AS ?objectCount) WHERE { GRAPH ?g { ?s ?p ?o } }"),
        "02-named-graph-counts": _query("SELECT ?g (COUNT(*) AS ?count) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g ORDER BY ?g"),
        "03-business-assertions": _query(f"SELECT ?s ?p ?o WHERE {{ GRAPH <{business}> {{ ?s ?p ?o . FILTER(?o IN (mnp:ReviewDecision, mnp:SourceRecord, owl:Class, owl:ObjectProperty, owl:DatatypeProperty, rdfs:Class, sh:NodeShape) || ?p IN (rdfs:subClassOf, rdfs:domain, rdfs:range, owl:equivalentClass)) }} }} ORDER BY ?s ?p ?o"),
        "04-provenance-coverage": _query(f"SELECT ?s ?p ?o WHERE {{ GRAPH <{business}> {{ ?s ?p ?o . FILTER(!(?p = rdf:type && ?o = owl:Ontology) && ?p != owl:imports) }} FILTER NOT EXISTS {{ GRAPH <{provenance}> {{ ?assertion a owl:Axiom ; owl:annotatedSource ?s ; owl:annotatedProperty ?p ; owl:annotatedTarget ?o ; mnp:hasReviewDecision ?decision }} }} }} ORDER BY ?s ?p ?o"),
        "05-review-audit-coverage": _query(f"SELECT (COUNT(*) AS ?count) WHERE {{ GRAPH <{review}> {{ ?s ?p ?o }} }}"),
        "06-tbox-version": _query("SELECT ?ontology ?version WHERE { GRAPH ?g { ?ontology a owl:Ontology ; owl:versionIRI ?version } } ORDER BY ?ontology"),
        "07-no-default-graph": _query("ASK { FILTER NOT EXISTS { ?s ?p ?o } }"),
        "08-no-tbox-in-business-graph": _query(f"ASK {{ FILTER NOT EXISTS {{ GRAPH <{business}> {{ ?s ?p ?o . FILTER(?o IN (owl:Class, owl:ObjectProperty, owl:DatatypeProperty, rdfs:Class) || ?p IN (rdfs:subClassOf, rdfs:domain, rdfs:range, owl:equivalentClass) || ?o = sh:NodeShape) }} }} }}"),
        "09-no-rejected-business-facts": _query(f"ASK {{ FILTER NOT EXISTS {{ GRAPH <{review}> {{ ?candidate ?decisionPredicate ?decisionValue . FILTER(CONTAINS(LCASE(STR(?decisionValue)), \"reject\") || CONTAINS(LCASE(STR(?decisionValue)), \"defer\")) }} GRAPH <{business}> {{ ?candidate ?p ?o }} }} }}"),
        "10-no-blank-nodes": _query("ASK { FILTER NOT EXISTS { GRAPH ?g { ?s ?p ?o . FILTER(isBlank(?s) || isBlank(?p) || isBlank(?o) || isBlank(?g)) } } }"),
    }
    normalized_expected = {key: int(value) for key, value in expected_counts.items()}
    content = {"contract_version": "1.0", "queries": queries, "expected": {"named_graphs": sorted({*named_graphs.values(), *stage06_graphs.values()}), "counts": normalized_expected, "tbox_module_count": tbox_modules, "ask": {"07-no-default-graph": True, "08-no-tbox-in-business-graph": True, "09-no-rejected-business-facts": True, "10-no-blank-nodes": True}}}
    query_bytes = b"".join((name + "\n" + queries[name]).encode("utf-8") for name in sorted(queries))
    content["normalization_policy"] = {"encoding": "UTF-8", "line_endings": "LF", "variables": "query declaration order", "rows": "RDF-term lexical order", "ask": "{boolean: bool}"}
    content["query_suite_hash"] = hashlib.sha256(query_bytes + canonical_json_bytes(content["expected"]) + canonical_json_bytes(content["normalization_policy"])).hexdigest()
    content["query_suite_id"] = f"urn:kg-mnp:graphdb-query-suite:{content['query_suite_hash']}"
    return content


def query_suite_hash(suite: Mapping[str, Any]) -> str:
    queries = suite["queries"]
    query_bytes = b"".join(
        (name + "\n" + str(queries[name])).encode("utf-8")
        for name in sorted(queries)
    )
    return hashlib.sha256(
        query_bytes
        + canonical_json_bytes(suite["expected"])
        + canonical_json_bytes(suite["normalization_policy"])
    ).hexdigest()
