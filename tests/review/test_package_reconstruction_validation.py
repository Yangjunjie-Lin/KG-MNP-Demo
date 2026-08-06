"""Independent package reconstruction validation tests."""

from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.canonical_json import semantic_hash
from kg_mnp_demo.modeling.identifiers import candidate_semantic_content
from kg_mnp_demo.modeling.review_identifiers import (
    confirmed_item_id,
    confirmed_package_id,
    package_semantic_hash,
)
from kg_mnp_demo.modeling.semantic_validation import (
    SemanticValidationError,
    validate_confirmed_modeling_package_semantics,
)

from ._helpers import (
    dependencies,
    load_expected_log,
    load_expected_package,
    load_input,
    load_proposal,
)


def _rehash_package(package: dict) -> dict:
    package = copy.deepcopy(package)
    digest = package_semantic_hash(package)
    package["package_semantic_hash"] = digest
    package["package_id"] = confirmed_package_id(digest)
    assert package["package_semantic_hash"] == package_semantic_hash(package)
    assert package["package_id"] == confirmed_package_id(package)
    return package


def _validate(package: dict, *, scenario: str, input_name: str) -> None:
    deps = dependencies()
    validate_confirmed_modeling_package_semantics(
        package,
        load_proposal(input_name),
        load_expected_log(scenario),
        cleaned_partial_data=load_input(input_name),
        ontology_baseline=deps["ontology_baseline"],
        mapping_rules=deps["mapping_rules"],
        terminology_profile=deps["terminology_profile"],
        proposal_policy=deps["proposal_policy"],
        review_policy=deps["review_policy"],
        term_types=deps["term_types"],
        require_complete=True,
    )


def test_rehashed_ready_forgery_rejected():
    package = copy.deepcopy(load_expected_package("deferred-review"))
    package["publication_manifest"]["package_status"] = "READY_FOR_COMPILATION"
    package["publication_manifest"]["compile_allowed"] = True
    package["publication_manifest"]["unresolved_blocking_issue_ids"] = []
    package = _rehash_package(package)
    with pytest.raises(
        SemanticValidationError,
        match="readiness derivation|deterministic reconstruction",
    ):
        _validate(package, scenario="deferred-review", input_name="conflicting-values")


def test_case_a_semantic_content_tamper_keeps_item_id():
    package = copy.deepcopy(load_expected_package("full-confirmation"))
    item = package["confirmed_abox_decisions"][0]
    content = copy.deepcopy(item["confirmed_candidate"]["semantic_content"])
    content["proposed_iri"] = content["proposed_iri"] + "-tampered"
    item["confirmed_candidate"]["semantic_content"] = content
    item["confirmed_candidate"]["semantic_hash"] = semantic_hash(content)
    package = _rehash_package(package)
    with pytest.raises(SemanticValidationError, match="deterministic reconstruction"):
        _validate(package, scenario="full-confirmation", input_name="partial-basic")


def test_case_b_rehashed_item_id_but_content_not_from_authority():
    package = copy.deepcopy(load_expected_package("full-confirmation"))
    item = package["confirmed_abox_decisions"][0]
    content = copy.deepcopy(item["confirmed_candidate"]["semantic_content"])
    content["rationale"] = content.get("rationale", "") + " tampered"
    item["confirmed_candidate"]["semantic_content"] = content
    item["confirmed_candidate"]["semantic_hash"] = semantic_hash(content)
    item["confirmed_candidate"]["confirmed_item_id"] = confirmed_item_id(
        source_candidate_id=item["confirmed_candidate"]["source_candidate_id"],
        effective_candidate_id=item["confirmed_candidate"]["effective_candidate_id"],
        confirmation_mode=item["confirmed_candidate"]["confirmation_mode"],
        semantic_content=content,
    )
    package = _rehash_package(package)
    with pytest.raises(SemanticValidationError, match="deterministic reconstruction"):
        _validate(package, scenario="full-confirmation", input_name="partial-basic")


def test_case_c_assertion_points_at_rejected_entity_after_rehash():
    package = copy.deepcopy(load_expected_package("rejection"))
    rejected = next(
        item["candidate_id"]
        for item in package["rejected_items"]
        if "candidate_id" in item
    )
    assertion = next(
        item
        for item in package["confirmed_abox_decisions"]
        if "predicate_iri" in item["confirmed_candidate"]["semantic_content"]
        or item["confirmed_candidate"]["semantic_content"].get("candidate_kind")
        in {"OBJECT_PROPERTY_ASSERTION", "DATA_PROPERTY_ASSERTION", "CLASS_ASSERTION"}
        or "subject_ref" in item["confirmed_candidate"]["semantic_content"]
    )
    content = copy.deepcopy(assertion["confirmed_candidate"]["semantic_content"])
    if "subject_ref" in content:
        content["subject_ref"] = rejected
    elif "object" in content and isinstance(content["object"], str):
        content["object"] = rejected
    else:
        content["subject_ref"] = rejected
    assertion["confirmed_candidate"]["semantic_content"] = content
    assertion["confirmed_candidate"]["semantic_hash"] = semantic_hash(
        candidate_semantic_content({**content, "candidate_id": "ignored"})
        if "candidate_id" not in content
        else content
    )
    # Keep envelope self-hashes consistent with content field.
    assertion["confirmed_candidate"]["semantic_hash"] = semantic_hash(content)
    assertion["confirmed_candidate"]["confirmed_item_id"] = confirmed_item_id(
        source_candidate_id=assertion["confirmed_candidate"]["source_candidate_id"],
        effective_candidate_id=assertion["confirmed_candidate"]["effective_candidate_id"],
        confirmation_mode=assertion["confirmed_candidate"]["confirmation_mode"],
        semantic_content=content,
    )
    package = _rehash_package(package)
    with pytest.raises(SemanticValidationError, match="deterministic reconstruction|non-confirmed"):
        _validate(package, scenario="rejection", input_name="partial-basic")


def test_legitimate_package_passes_reconstruction():
    package = load_expected_package("full-confirmation")
    _validate(package, scenario="full-confirmation", input_name="partial-basic")
