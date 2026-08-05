"""Terminology aliases assist review without minting ontology semantics."""

from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.dependencies import (
    ROOT,
    load_modeling_dependencies,
    normalized_file_hash,
)
from kg_mnp_demo.modeling.registry import validate_contract
from kg_mnp_demo.modeling.semantic_validation import (
    SemanticValidationError,
    validate_terminology_profile_semantics,
)


def _dependencies() -> dict:
    return load_modeling_dependencies()


def _validate(profile: dict, dependencies: dict) -> None:
    validate_terminology_profile_semantics(
        profile,
        dependencies["ontology_baseline"],
        term_iris=dependencies["term_iris"],
    )


def test_profile_validates_offline_and_uses_inventory_terms_only():
    dependencies = _dependencies()
    profile = dependencies["terminology_profile"]
    validate_contract("terminology-profile", profile)
    _validate(profile, dependencies)
    assert profile["profile_version"] == "1.0.0"
    assert profile["ontology_version"] == "1.0.0"
    assert {
        entry["term_iri"] for entry in profile["entries"]
    } <= dependencies["term_iris"]
    assert len(dependencies["term_iris"]) == 211


def test_unknown_term_iri_fails_closed():
    dependencies = _dependencies()
    profile = copy.deepcopy(dependencies["terminology_profile"])
    profile["entries"][0]["term_iri"] = "https://invalid.example/ontology#Unknown"
    with pytest.raises(SemanticValidationError, match="absent from ontology baseline"):
        _validate(profile, dependencies)


def test_undeclared_ambiguous_alias_fails_closed():
    dependencies = _dependencies()
    profile = copy.deepcopy(dependencies["terminology_profile"])
    profile["entries"][0]["aliases"].append("shared term")
    profile["entries"][1]["aliases"].append("Shared   Term")
    with pytest.raises(SemanticValidationError, match="ambiguous alias"):
        _validate(profile, dependencies)


def test_exact_ambiguity_group_passes_without_selecting_a_term():
    dependencies = _dependencies()
    profile = copy.deepcopy(dependencies["terminology_profile"])
    first = profile["entries"][0]["term_iri"]
    second = profile["entries"][1]["term_iri"]
    profile["entries"][0]["aliases"].append("shared term")
    profile["entries"][1]["aliases"].append("Shared   Term")
    profile["ambiguity_groups"] = [
        {
            "group_id": "shared-term",
            "normalized_form": "shared term",
            "term_iris": [first, second],
            "rationale": "Synthetic validation fixture; no preferred term is selected.",
        }
    ]
    validate_contract("terminology-profile", profile)
    _validate(profile, dependencies)
    assert "selected_term_iri" not in profile["ambiguity_groups"][0]


def test_mismatched_ambiguity_group_fails_closed():
    dependencies = _dependencies()
    profile = copy.deepcopy(dependencies["terminology_profile"])
    first = profile["entries"][0]["term_iri"]
    second = profile["entries"][1]["term_iri"]
    third = profile["entries"][2]["term_iri"]
    profile["entries"][0]["aliases"].append("shared term")
    profile["entries"][1]["aliases"].append("shared term")
    profile["ambiguity_groups"] = [
        {"normalized_form": "shared term", "term_iris": [first, second, third]}
    ]
    with pytest.raises(SemanticValidationError, match="ambiguity group"):
        _validate(profile, dependencies)


def test_alias_validation_does_not_rewrite_or_extend_owl_assets():
    ontology_paths = sorted((ROOT / "ontology").glob("*.ttl"))
    before = {path: normalized_file_hash(path) for path in ontology_paths}
    dependencies = _dependencies()
    _validate(dependencies["terminology_profile"], dependencies)
    after = {path: normalized_file_hash(path) for path in ontology_paths}
    assert after == before
    profile = dependencies["terminology_profile"]
    assert "equivalence" not in profile
    assert all("equivalence" not in entry for entry in profile["entries"])
