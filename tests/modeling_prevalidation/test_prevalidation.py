from __future__ import annotations

import copy

import pytest
from jsonschema import ValidationError

from kg_mnp.modeling.control_plane.errors import ModelingProposalError
from kg_mnp.modeling.control_plane.prevalidation import CHECKS, verify_prevalidation


def test_all_thirty_checks_are_reported_without_final_validation_claims(
    prompt04_case: dict,
) -> None:
    report = prompt04_case["prevalidation"]
    assert len(CHECKS) == 30
    assert [item["check_id"] for item in report["checks"]] == list(CHECKS)
    assert report["status"] == "REVIEW_REQUIRED"
    assert report["owl_consistency_claimed"] is False
    assert report["shacl_execution_claimed"] is False
    assert report["cq_execution_claimed"] is False


def test_stale_proposal_and_false_final_claim_are_rejected(prompt04_case: dict) -> None:
    changed = copy.deepcopy(prompt04_case["proposal"])
    changed["content_digest"] = "f" * 64
    with pytest.raises(ModelingProposalError, match="STALE"):
        verify_prevalidation(prompt04_case["prevalidation"], proposal=changed)
    claimed = copy.deepcopy(prompt04_case["prevalidation"])
    claimed["owl_consistency_claimed"] = True
    with pytest.raises((ModelingProposalError, ValidationError)):
        verify_prevalidation(claimed)
