import copy

import pytest

from kg_mnp_demo.compilation.abox_compiler import ABoxCompilationError, compile_abox
from kg_mnp_demo.compilation.candidate_resolution import (
    CandidateResolutionError,
    resolve_effective_candidates,
    resolve_effective_entity_iris,
)
from ._helpers import authorities


def test_all_confirmed_entities_resolve_to_effective_iris():
    values = authorities()
    resolved = resolve_effective_candidates(values[3], values[1])
    iris = resolve_effective_entity_iris(values[3], values[1])
    assert resolved and iris
    assert all(value.startswith(("http://", "https://")) for value in iris.values())


def test_duplicate_effective_entity_iri_is_rejected():
    values = list(authorities())
    proposal = copy.deepcopy(values[1])
    first, second = proposal["candidate_entities"][:2]
    second["proposed_iri"] = first["proposed_iri"]
    with pytest.raises(CandidateResolutionError, match="duplicate entity IRI"):
        compile_abox(values[3], proposal, values[4])


def test_reserved_ontology_namespace_is_rejected_for_instance_iri():
    values = list(authorities())
    proposal = copy.deepcopy(values[1])
    proposal["candidate_entities"][0]["proposed_iri"] = (
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#forged-instance"
    )
    with pytest.raises(ABoxCompilationError, match="reserved namespace"):
        compile_abox(values[3], proposal, values[4])
