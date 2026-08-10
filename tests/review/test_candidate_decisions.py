from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.review_actions import validate_review_action

from ._helpers import load_action, load_proposal


@pytest.mark.parametrize(
    ("scenario", "filename", "decision"),
    [
        ("full-confirmation", "action-001.json", "CONFIRM"),
        ("modified-confirmation", "action-002.json", "MODIFY_AND_CONFIRM"),
        ("rejection", "action-002.json", "REJECT"),
    ],
)
def test_candidate_decisions_pass(scenario, filename, decision):
    proposal = load_proposal()
    action = load_action(scenario, filename)
    assert action["decision"] == decision
    validate_review_action(action, proposal)


def test_candidate_deprecate_fails():
    proposal = load_proposal()
    action = load_action("full-confirmation", "action-001.json")
    action = copy.deepcopy(action)
    action["decision"] = "DEPRECATE"
    with pytest.raises(Exception):
        validate_review_action(action, proposal)
