"""ReviewDecisionLog contract-only tests; no workflow is implemented here."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from kg_mnp_demo.modeling.registry import validate_contract
from kg_mnp_demo.modeling.semantic_validation import (
    SemanticValidationError,
    validate_review_decision_log_semantics,
)

from .test_modeling_proposal_contract import CANDIDATE_ID, HASH, candidate_entity

ROOT = Path(__file__).resolve().parents[2]


def decision_log() -> dict[str, object]:
    return {
        "contract_version": "1.0",
        "decision_log_id": "review-log-001",
        "proposal_id": "urn:kg-mnp:modeling-proposal:" + "c" * 64,
        "proposal_semantic_hash": HASH,
        "reviewer": {"reviewer_id": "reviewer-001", "role": "ONTOLOGY_REVIEWER"},
        "review_session": {
            "session_id": "session-001",
            "started_at": "2026-08-01T00:00:00Z",
        },
        "decisions": [],
        "log_hash": HASH,
    }


def review_decision(value: str = "CONFIRM") -> dict[str, object]:
    return {
        "decision_id": "decision-001",
        "candidate_id": CANDIDATE_ID,
        "decision": value,
        "rationale": "Human review rationale.",
        "reviewer_id": "reviewer-001",
        "decided_at": "2026-08-01T01:00:00Z",
        "evidence_refs": ["review-evidence-001"],
    }


def test_empty_review_session_log_is_schema_valid():
    validate_contract("review-decision-log", decision_log())


@pytest.mark.parametrize(
    "decision",
    ["CONFIRM", "REJECT", "DEFER", "DEPRECATE"],
)
def test_closed_human_decision_vocabulary(decision: str):
    payload = decision_log()
    payload["decisions"] = [review_decision(decision)]

    validate_contract("review-decision-log", payload)


def test_modify_and_confirm_requires_a_complete_modified_candidate():
    payload = decision_log()
    decision = review_decision("MODIFY_AND_CONFIRM")
    decision["modified_candidate"] = candidate_entity()
    payload["decisions"] = [decision]
    validate_contract("review-decision-log", payload)

    invalid = copy.deepcopy(payload)
    invalid["decisions"][0].pop("modified_candidate")
    with pytest.raises(ValidationError):
        validate_contract("review-decision-log", invalid)


def test_modified_candidate_is_forbidden_for_other_decisions():
    payload = decision_log()
    decision = review_decision("CONFIRM")
    decision["modified_candidate"] = candidate_entity()
    payload["decisions"] = [decision]

    with pytest.raises(ValidationError):
        validate_contract("review-decision-log", payload)


def test_each_decision_targets_exactly_one_candidate_or_issue():
    payload = decision_log()
    decision = review_decision()
    decision["issue_id"] = "urn:kg-mnp:issue:" + "d" * 64
    payload["decisions"] = [decision]

    with pytest.raises(ValidationError):
        validate_contract("review-decision-log", payload)


@pytest.mark.parametrize("invalid", ["APPROVE", "PROPOSED", "AUTO_CONFIRM"])
def test_unknown_or_status_like_decisions_fail(invalid: str):
    payload = decision_log()
    payload["decisions"] = [review_decision(invalid)]

    with pytest.raises(ValidationError):
        validate_contract("review-decision-log", payload)


def test_semantic_validator_resolves_decisions_only_to_proposal_items():
    proposal = json.loads(
        (ROOT / "examples/modeling/expected-proposals/partial-basic.proposal.json").read_text(
            encoding="utf-8"
        )
    )
    fixture = json.loads(
        (ROOT / "tests/fixtures/modeling/review-decision-log.valid.json").read_text(
            encoding="utf-8"
        )
    )
    validate_review_decision_log_semantics(fixture, proposal)

    invalid = copy.deepcopy(fixture)
    invalid["decisions"][0]["candidate_id"] = "urn:kg-mnp:candidate:" + "f" * 64
    with pytest.raises(SemanticValidationError, match="unknown candidate_id"):
        validate_review_decision_log_semantics(invalid, proposal)
