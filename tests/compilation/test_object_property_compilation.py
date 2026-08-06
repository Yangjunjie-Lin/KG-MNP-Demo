import copy

import pytest
from rdflib import URIRef

from kg_mnp_demo.compilation.abox_compiler import ABoxCompilationError, compile_abox
from kg_mnp_demo.compilation.candidate_resolution import CandidateResolutionError
from ._helpers import authorities


def test_object_property_uses_effective_entity_iris():
    values = authorities()
    graph, assertions = compile_abox(values[3], values[1], values[4])
    relation = next(item for item in assertions if item.candidate_kind == "OBJECT_PROPERTY_ASSERTION")
    assert isinstance(relation.triple[0], URIRef) and isinstance(relation.triple[2], URIRef)


@pytest.mark.parametrize("field", ["subject_ref", "object"])
def test_unconfirmed_object_property_endpoint_is_rejected(field):
    values = list(authorities())
    proposal = copy.deepcopy(values[1])
    relation = next(
        item for item in proposal["candidate_assertions"]
        if item["candidate_kind"] == "OBJECT_PROPERTY_ASSERTION"
    )
    relation[field] = "urn:kg-mnp:candidate:unconfirmed"
    with pytest.raises((ABoxCompilationError, CandidateResolutionError)):
        compile_abox(values[3], proposal, values[4])


def test_modify_and_confirm_uses_effective_entity_iri():
    values = list(authorities("modified-confirmation"))
    package = copy.deepcopy(values[3])
    modified = next(
        item for item in package["confirmed_abox_decisions"]
        if item["decision"] == "MODIFY_AND_CONFIRM"
    )
    source_id = modified["confirmed_candidate"]["source_candidate_id"]
    source = next(item for item in values[1]["candidate_entities"] if item["candidate_id"] == source_id)
    old_iri = URIRef(source["proposed_iri"])
    new_iri = "https://yangjunjie-lin.github.io/KG-MNP-Demo/data/audit-effective-entity"
    modified["confirmed_candidate"]["semantic_content"]["proposed_iri"] = new_iri

    graph, assertions = compile_abox(package, values[1], values[4])

    assert any(new_iri in {str(item.triple[0]), str(item.triple[2])} for item in assertions)
    assert all(old_iri not in triple for triple in graph)
