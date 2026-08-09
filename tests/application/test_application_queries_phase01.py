from __future__ import annotations

from kg_mnp_demo.application.query_registry import QueryRegistry
from kg_mnp_demo.application.service import ApplicationService

from ._phase01_helpers import DatasetClient, synthetic_binding

SUBSCRIPTION = "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/modeled/2993a1403cabddd34da97cacad8c5aa55103903ab9d3a0d831bd9f989f2fc029"
STATUS = "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#subscriptionStatusCode"
SUBSCRIBER = "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/modeled/3c57cca129580c393bb6994fbf088209879907efde712279eb6de9986ba6d457"
REJECTED_CANDIDATE = "urn:kg-mnp:candidate:5b68a78bcd602a16e687f82b44570cf02bbc5df37e7e4b290accc6052db7014a"


def service(scenario="full-confirmation"):
    return ApplicationService(
        binding=synthetic_binding(scenario),
        registry=QueryRegistry.load(),
        client=DatasetClient(scenario),
    )


def literal_active():
    return {"term_type": "LITERAL", "value": "ACTIVE", "datatype_iri": "http://www.w3.org/2001/XMLSchema#string", "language": None}


def test_entity_and_ontology_queries_are_bounded_and_named_graph_only():
    entity = service().run("business.entity", {"iri": SUBSCRIPTION, "limit": 100, "offset": 0})
    assert entity["result_count"] == 3
    assert entity["truncated"] is False
    assert entity["traceability"]["graphdb"]["graph_iris"]
    classes = service().run("ontology.classes", {"limit": 20, "offset": 0})
    assert 0 < classes["result_count"] <= 20
    assert all(":graph:tbox:" in iri for iri in classes["traceability"]["graphdb"]["graph_iris"])


def test_exact_fact_provenance_closes_review_evidence_source_and_publication_lineage():
    result = service().run(
        "provenance.fact",
        {"subject": SUBSCRIPTION, "predicate": STATUS, "object": literal_active(), "limit": 100, "offset": 0},
    )
    trace = result["traceability"]
    assert result["result_count"] >= 1
    assert trace["business_facts"][0]["object"] == {
        "term_type": "LITERAL",
        "lexical_form": "ACTIVE",
        "datatype_iri": "http://www.w3.org/2001/XMLSchema#string",
        "language": None,
    }
    assert trace["modeling"][0]["candidate_id"].startswith("urn:kg-mnp:candidate:")
    assert trace["review"][0]["outcome"] == "CONFIRM"
    assert trace["evidence"] and trace["source"]
    assert trace["publication"]["publication_id"].startswith("urn:kg-mnp:e2e-publication:")


def test_semantic_hash_excludes_runtime_metadata_and_order_is_deterministic():
    first = service().run("business.entity", {"iri": SUBSCRIPTION, "limit": 100, "offset": 0})
    second = service().run("business.entity", {"iri": SUBSCRIPTION, "limit": 100, "offset": 0})
    assert first["results"] == second["results"]
    assert first["result_semantic_hash"] == second["result_semantic_hash"]
    assert first["runtime_metadata"] != second["runtime_metadata"]


def test_rejected_candidate_is_absent_from_business_plane_but_visible_in_review_plane():
    rejected = service("rejection")
    business = rejected.run("business.entity", {"iri": SUBSCRIBER, "limit": 100, "offset": 0})
    review = rejected.run("review.trace", {"resource_id": REJECTED_CANDIDATE, "limit": 100, "offset": 0})
    assert business["result_count"] == 0
    assert review["result_count"] == 1
    outcome = next(binding["term"] for binding in review["results"][0]["bindings"] if binding["variable"] == "outcome")
    assert outcome["lexical_form"] == "REJECT"
