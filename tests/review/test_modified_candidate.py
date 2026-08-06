from __future__ import annotations

import copy

import pytest
from jsonschema import ValidationError

from kg_mnp_demo.modeling.identifiers import candidate_id
from kg_mnp_demo.modeling.review_actions import validate_review_action
from kg_mnp_demo.modeling.semantic_validation import SemanticValidationError

from ._helpers import dependencies, load_action, load_proposal


def test_modify_and_confirm_preserves_sources_and_kind():
    proposal = load_proposal()
    action = load_action("modified-confirmation", "action-002.json")
    validate_review_action(action, proposal, term_types=dependencies()["term_types"])
    modified = action["modified_candidate"]
    original = next(
        item
        for item in proposal["candidate_entities"]
        if item["candidate_id"] == action["target"]["candidate_id"]
    )
    assert modified.get("candidate_kind", "ENTITY") == original.get("candidate_kind", "ENTITY")
    assert set(original["source_paths"]).issubset(set(modified["source_paths"]))
    assert modified["candidate_id"] == candidate_id(modified)
    assert modified["candidate_id"] != original["candidate_id"]


def test_modified_candidate_rejects_kind_and_tbox_changes():
    proposal = load_proposal()
    action = copy.deepcopy(load_action("modified-confirmation", "action-002.json"))
    action["modified_candidate"]["candidate_kind"] = "DATA_PROPERTY_ASSERTION"
    with pytest.raises((SemanticValidationError, ValidationError)):
        validate_review_action(action, proposal, term_types=dependencies()["term_types"])
    action = copy.deepcopy(load_action("modified-confirmation", "action-002.json"))
    action["modified_candidate"]["publication_scope"] = "TBOX"
    with pytest.raises((SemanticValidationError, ValidationError)):
        validate_review_action(action, proposal, term_types=dependencies()["term_types"])


def test_modified_candidate_rejects_unknown_term():
    proposal = load_proposal()
    action = copy.deepcopy(load_action("modified-confirmation", "action-002.json"))
    action["modified_candidate"]["class_iri"] = (
        "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#NotARealClass"
    )
    action["modified_candidate"]["candidate_id"] = candidate_id(action["modified_candidate"])
    with pytest.raises(SemanticValidationError, match="owl:Class"):
        validate_review_action(action, proposal, term_types=dependencies()["term_types"])
