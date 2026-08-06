from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.identifiers import candidate_id
from kg_mnp_demo.modeling.review_actions import validate_candidate_term_types
from kg_mnp_demo.modeling.semantic_validation import SemanticValidationError

from ._helpers import dependencies, load_proposal


def test_predicate_and_class_term_types_are_enforced():
    proposal = load_proposal()
    types = dependencies()["term_types"]
    entity = proposal["candidate_entities"][0]
    assert validate_candidate_term_types(entity, types) == []
    data = next(
        item
        for item in proposal["candidate_assertions"]
        if item["candidate_kind"] == "DATA_PROPERTY_ASSERTION"
    )
    assert validate_candidate_term_types(data, types) == []
    bad = copy.deepcopy(data)
    bad["predicate_iri"] = entity["class_iri"]
    bad["candidate_id"] = candidate_id(bad)
    errors = validate_candidate_term_types(bad, types)
    assert errors
    assert "DatatypeProperty" in errors[0]
