from __future__ import annotations

from copy import deepcopy

import pytest

from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.proposal import generate_modeling_proposal
from kg_mnp_demo.modeling.semantic_validation import (
    SemanticValidationError,
    validate_proposal_policy_semantics,
)

from ._helpers import generate, load_input


def test_low_confidence_creates_issues_but_never_confirms() -> None:
    proposal = generate("low-confidence-source")
    candidates = [*proposal["candidate_entities"], *proposal["candidate_assertions"]]
    assert candidates
    assert all(candidate["review_status"] == "PROPOSED" for candidate in candidates)
    assert any(issue["issue_type"] == "LOW_CONFIDENCE" for issue in proposal["issues"])
    assert all(candidate["confidence"]["components"] for candidate in candidates)


def test_high_confidence_still_remains_proposed() -> None:
    candidates = generate("partial-basic")["candidate_assertions"]
    high = [item for item in candidates if item["confidence"]["level"] == "HIGH"]
    assert high and all(item["review_status"] == "PROPOSED" for item in high)


def test_confidence_policy_is_explicit_and_frozen() -> None:
    policy = load_modeling_dependencies()["proposal_policy"]
    validate_proposal_policy_semantics(policy)
    invalid = deepcopy(policy)
    invalid["confidence_combination_policy"] = "HIDDEN_FORMULA"
    with pytest.raises(SemanticValidationError):
        validate_proposal_policy_semantics(invalid)


def test_declared_confidence_level_must_match_its_score_range() -> None:
    dependencies = load_modeling_dependencies()
    cleaned = load_input("partial-basic")
    cleaned["field_metadata"][0]["confidence"]["level"] = "LOW"
    with pytest.raises(ValueError, match="does not match policy"):
        generate_modeling_proposal(
            cleaned,
            dependencies["ontology_baseline"],
            dependencies["mapping_rules"],
            dependencies["terminology_profile"],
            dependencies["proposal_policy"],
            term_iris=set(dependencies["term_iris"]),
        )
