"""ConfirmedModelingPackage shape tests; Stage 04 has no package builder."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from kg_mnp_demo.modeling.registry import validate_contract
from kg_mnp_demo.modeling.semantic_validation import (
    SemanticValidationError,
    validate_confirmed_modeling_package_semantics,
)

from .test_modeling_proposal_contract import CANDIDATE_ID, HASH

ROOT = Path(__file__).resolve().parents[2]


def confirmed_package() -> dict[str, object]:
    return {
        "contract_version": "1.0",
        "package_id": "confirmed-package-fixture-001",
        "package_semantic_hash": HASH,
        "source_proposal_id": "urn:kg-mnp:modeling-proposal:" + "c" * 64,
        "source_proposal_hash": HASH,
        "review_decision_log_id": "review-log-001",
        "review_decision_log_hash": HASH,
        "ontology_baseline": {
            "ontology_baseline_id": "ontology-baseline-001",
            "ontology_version": "1.0.0",
            "ontology_release_source_hash": HASH,
        },
        "confirmed_abox_decisions": [],
        "confirmed_schema_delta": [],
        "rejected_items": [],
        "deferred_items": [],
        "publication_manifest": {},
    }


def test_empty_contract_fixture_is_valid_but_does_not_build_a_package():
    validate_contract("confirmed-modeling-package", confirmed_package())


@pytest.mark.parametrize("decision", ["CONFIRM", "MODIFY_AND_CONFIRM"])
def test_abox_section_accepts_only_effective_confirmation_decisions(decision: str):
    payload = confirmed_package()
    payload["confirmed_abox_decisions"] = [
        {
            "decision_id": "decision-001",
            "candidate_id": CANDIDATE_ID,
            "decision": decision,
            "publication_scope": "ABOX",
        }
    ]

    validate_contract("confirmed-modeling-package", payload)


def test_reject_and_defer_cannot_enter_confirmed_sections():
    for decision in ("REJECT", "DEFER"):
        payload = confirmed_package()
        payload["confirmed_abox_decisions"] = [
            {
                "decision_id": "decision-001",
                "candidate_id": CANDIDATE_ID,
                "decision": decision,
                "publication_scope": "ABOX",
            }
        ]
        with pytest.raises(ValidationError):
            validate_contract("confirmed-modeling-package", payload)


def test_confirmed_schema_delta_requires_tbox_scope():
    payload = confirmed_package()
    payload["confirmed_schema_delta"] = [
        {
            "decision_id": "decision-001",
            "candidate_id": CANDIDATE_ID,
            "decision": "CONFIRM",
            "publication_scope": "ABOX",
        }
    ]

    with pytest.raises(ValidationError):
        validate_contract("confirmed-modeling-package", payload)


def test_rejected_and_deferred_sections_preserve_the_decision_kind():
    payload = confirmed_package()
    payload["rejected_items"] = [
        {
            "decision_id": "decision-reject",
            "candidate_id": CANDIDATE_ID,
            "decision": "REJECT",
        }
    ]
    payload["deferred_items"] = [
        {
            "decision_id": "decision-defer",
            "issue_id": "urn:kg-mnp:issue:" + "d" * 64,
            "decision": "DEFER",
        }
    ]

    validate_contract("confirmed-modeling-package", payload)

    invalid = copy.deepcopy(payload)
    invalid["deferred_items"][0]["decision"] = "REJECT"
    with pytest.raises(ValidationError):
        validate_contract("confirmed-modeling-package", invalid)


def test_wrong_contract_version_and_top_level_extras_fail():
    for field, value in (("contract_version", "2.0"), ("auto_confirmed", True)):
        payload = confirmed_package()
        payload[field] = value
        with pytest.raises(ValidationError):
            validate_contract("confirmed-modeling-package", payload)


def test_semantic_validator_requires_the_effective_review_decision():
    proposal = json.loads(
        (ROOT / "examples/modeling/expected-proposals/partial-basic.proposal.json").read_text(
            encoding="utf-8"
        )
    )
    decision_log = json.loads(
        (ROOT / "tests/fixtures/modeling/review-decision-log.valid.json").read_text(
            encoding="utf-8"
        )
    )
    package = json.loads(
        (ROOT / "tests/fixtures/modeling/confirmed-modeling-package.valid.json").read_text(
            encoding="utf-8"
        )
    )
    validate_confirmed_modeling_package_semantics(package, proposal, decision_log)

    invalid = copy.deepcopy(package)
    invalid["confirmed_abox_decisions"][0]["decision_id"] = "unrelated-decision"
    with pytest.raises(SemanticValidationError, match="review decision"):
        validate_confirmed_modeling_package_semantics(invalid, proposal, decision_log)

    wrong_hash = copy.deepcopy(package)
    wrong_hash["review_decision_log_hash"] = "c" * 64
    with pytest.raises(SemanticValidationError, match="review_decision_log_hash"):
        validate_confirmed_modeling_package_semantics(wrong_hash, proposal, decision_log)
