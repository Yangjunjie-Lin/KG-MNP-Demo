from __future__ import annotations

import pytest

from kg_mnp_demo.governance.errors import GovernanceError, GovernanceErrorCode
from kg_mnp_demo.governance.state_machine import require_transition
from kg_mnp_demo.governance.workspace import GovernanceWorkspace

from ._helpers import authority, proposal_arguments


def _submitted():
    auth = authority()
    workspace = GovernanceWorkspace.initialize(auth)
    proposal = workspace.create_proposal(
        expected_workspace_revision=0, **proposal_arguments(auth)
    )
    workspace.submit_proposal(proposal["proposal_id"], expected_workspace_revision=1)
    return workspace, proposal


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("DRAFT", "APPROVED_FOR_AMENDMENT"),
        ("REJECTED", "APPROVED_FOR_AMENDMENT"),
        ("APPROVED_FOR_AMENDMENT", "DRAFT"),
        ("DEFERRED", "APPROVED_FOR_AMENDMENT"),
    ],
)
def test_illegal_transitions_are_rejected(current: str, target: str) -> None:
    with pytest.raises(GovernanceError) as caught:
        require_transition(current, target)
    assert caught.value.code in {
        GovernanceErrorCode.ILLEGAL_STATE_TRANSITION,
        GovernanceErrorCode.TERMINAL_STATE_IMMUTABLE,
    }


@pytest.mark.parametrize(
    ("decision", "expected_status", "has_amendment"),
    [
        ("APPROVE_FOR_AMENDMENT", "APPROVED_FOR_AMENDMENT", True),
        ("REJECT", "REJECTED", False),
        ("DEFER", "DEFERRED", False),
    ],
)
def test_explicit_review_transitions(
    decision: str, expected_status: str, has_amendment: bool
) -> None:
    workspace, proposal = _submitted()
    result = workspace.review_proposal(
        proposal["proposal_id"],
        decision=decision,
        review_note="Explicit human review note",
        reviewed_by_label="operator-supplied reviewer label",
        explicit_human_action=True,
        expected_workspace_revision=2,
    )
    state = workspace.reconstruct()
    current = next(
        p for p in state["proposals"] if p["proposal_id"] == proposal["proposal_id"]
    )
    assert current["status"] == expected_status
    assert (result["amendment_request"] is not None) is has_amendment
    if has_amendment:
        request = result["amendment_request"]
        assert request["status"] == "APPROVED_FOR_FUTURE_MODELING_AMENDMENT"
        assert request["governance_status"] == "APPROVED_FOR_FUTURE_AMENDMENT"
        assert "diagnostic_status" not in request


def test_human_action_cannot_be_inferred_or_automated() -> None:
    workspace, proposal = _submitted()
    with pytest.raises(GovernanceError, match="explicit human action"):
        workspace.review_proposal(
            proposal["proposal_id"],
            decision="APPROVE_FOR_AMENDMENT",
            review_note="automated",
            reviewed_by_label="rule",
            explicit_human_action=False,
            expected_workspace_revision=2,
        )
