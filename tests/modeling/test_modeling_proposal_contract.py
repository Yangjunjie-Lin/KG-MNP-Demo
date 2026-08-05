"""ModelingProposal JSON Schema boundaries."""

from __future__ import annotations

import copy

import pytest
from jsonschema import ValidationError

from kg_mnp_demo.modeling.registry import validate_contract


HASH = "a" * 64
CANDIDATE_ID = "urn:kg-mnp:candidate:" + "b" * 64


def minimal_proposal() -> dict[str, object]:
    return {
        "contract_version": "1.0",
        "proposal_id": "urn:kg-mnp:modeling-proposal:" + "c" * 64,
        "proposal_semantic_hash": HASH,
        "run_mode": "DATASET_MODELING",
        "input_snapshot": {
            "document_id": "document-001",
            "dataset_id": "dataset-001",
            "input_contract_version": "1.0",
            "input_semantic_hash": HASH,
        },
        "dependency_snapshot": {
            "ontology_baseline_id": "baseline-001",
            "ontology_version": "1.0.0",
            "ontology_release_source_hash": HASH,
            "mapping_set_id": "mapping-set-001",
            "mapping_set_version": "1.0.0",
            "mapping_rules_hash": HASH,
            "terminology_profile_id": "profile-001",
            "terminology_profile_version": "1.0.0",
            "terminology_profile_hash": HASH,
            "proposal_policy_version": "1.0.0",
            "proposal_policy_hash": HASH,
            "generator_version": "1.0.0",
        },
        "candidate_entities": [],
        "candidate_assertions": [],
        "schema_delta_candidates": [],
        "issues": [],
        "unmapped_fields": [],
        "summary": {
            "candidate_entity_count": 0,
            "candidate_assertion_count": 0,
            "issue_count": 0,
            "unmapped_field_count": 0,
            "schema_delta_count": 0,
        },
    }


def candidate_entity() -> dict[str, object]:
    return {
        "candidate_id": CANDIDATE_ID,
        "review_status": "PROPOSED",
        "publication_scope": "ABOX",
        "proposed_iri": "https://example.com/data/entity-1",
        "class_iri": "https://example.com/ontology/Entity",
        "source_paths": ["/entity/id"],
        "mapping_rule_ids": ["entity-rule"],
        "business_fact_evidence_refs": ["source-1"],
        "modeling_evidence_refs": ["mapping-reference-1"],
        "confidence": {
            "level": "HIGH",
            "score": 0.9,
            "basis": "RULE_AND_SOURCE",
            "components": [
                {
                    "component": "MAPPING_RULE",
                    "level": "HIGH",
                    "score": 0.9,
                    "basis": "RULE_DECLARED",
                }
            ],
        },
        "rationale": "A confirmed mapping rule generated a review-only entity candidate.",
    }


def test_minimal_review_only_proposal_is_valid():
    validate_contract("modeling-proposal", minimal_proposal())


def test_candidate_entity_must_remain_proposed():
    payload = minimal_proposal()
    entity = candidate_entity()
    payload["candidate_entities"] = [entity]
    payload["summary"]["candidate_entity_count"] = 1
    validate_contract("modeling-proposal", payload)

    invalid = copy.deepcopy(payload)
    invalid["candidate_entities"][0]["review_status"] = "CONFIRMED"
    with pytest.raises(ValidationError):
        validate_contract("modeling-proposal", invalid)


def test_schema_delta_candidates_are_structurally_locked_empty():
    payload = minimal_proposal()
    payload["schema_delta_candidates"] = [{"candidate_kind": "NEW_CLASS"}]

    with pytest.raises(ValidationError):
        validate_contract("modeling-proposal", payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("contract_version", "2.0"),
        ("run_mode", "ONTOLOGY_RELEASE"),
        ("unexpected", True),
    ],
)
def test_wrong_version_mode_and_additional_properties_fail(field: str, value: object):
    payload = minimal_proposal()
    payload[field] = value

    with pytest.raises(ValidationError):
        validate_contract("modeling-proposal", payload)


def test_issue_status_and_scope_are_review_only():
    payload = minimal_proposal()
    payload["issues"] = [
        {
            "issue_id": "urn:kg-mnp:issue:" + "d" * 64,
            "issue_type": "LOW_CONFIDENCE",
            "severity": "WARNING",
            "review_status": "CONFIRMED",
            "publication_scope": "REVIEW_ONLY",
            "source_paths": ["/entity/id"],
            "source_refs": ["source-1"],
            "related_candidate_ids": [],
            "description": "Review required.",
            "blocking": False,
        }
    ]

    with pytest.raises(ValidationError):
        validate_contract("modeling-proposal", payload)
