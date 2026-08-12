from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.governance.errors import GovernanceError, GovernanceErrorCode
from kg_mnp_demo.governance.validator import (
    validate_governance_workspace_against_authorities,
    workspace_semantic_content,
)
from kg_mnp_demo.governance.workspace import GovernanceWorkspace
from kg_mnp_demo.modeling.canonical_json import semantic_hash

from ._helpers import authority, proposal_arguments, stale


def _approved():
    auth = authority()
    workspace = GovernanceWorkspace.initialize(auth)
    proposal = workspace.create_proposal(
        expected_workspace_revision=0, **proposal_arguments(auth)
    )
    workspace.submit_proposal(proposal["proposal_id"], expected_workspace_revision=1)
    workspace.review_proposal(
        proposal["proposal_id"],
        decision="APPROVE_FOR_AMENDMENT",
        review_note="Approve only for future modeling amendment",
        reviewed_by_label="reviewer label",
        explicit_human_action=True,
        expected_workspace_revision=2,
    )
    return auth, workspace


@pytest.mark.parametrize("attack", ["delete", "insert", "reorder", "modify"])
def test_event_chain_detects_structural_tampering(attack: str) -> None:
    auth, workspace = _approved()
    attacked = copy.deepcopy(workspace.value)
    if attack == "delete":
        del attacked["events"][1]
    elif attack == "insert":
        attacked["events"].insert(1, copy.deepcopy(attacked["events"][0]))
    elif attack == "reorder":
        attacked["events"][0], attacked["events"][1] = (
            attacked["events"][1],
            attacked["events"][0],
        )
    else:
        attacked["events"][0]["payload"]["rationale"] = "tampered"
    with pytest.raises(GovernanceError) as caught:
        validate_governance_workspace_against_authorities(attacked, auth)
    assert caught.value.code == GovernanceErrorCode.WORKSPACE_TAMPERED


def test_self_consistent_rehash_is_rejected_by_trusted_head_anchor() -> None:
    auth, workspace = _approved()
    original = workspace.value["workspace_hash"]
    attacked = copy.deepcopy(workspace.value)
    review = attacked["events"][2]
    review["payload"]["review_note"] = "attacker changed and will rehash"
    previous = "GENESIS"
    for index, event in enumerate(attacked["events"], start=1):
        event["sequence"] = index
        event["previous_event_hash"] = previous
        event["payload_hash"] = semantic_hash(event["payload"])
        event["event_id"] = semantic_hash(
            {
                "sequence": event["sequence"],
                "previous_event_hash": previous,
                "event_type": event["event_type"],
                "payload_hash": event["payload_hash"],
            }
        )
        previous = event["event_id"]
    attacked["head_event_hash"] = previous
    attacked["workspace_hash"] = semantic_hash(workspace_semantic_content(attacked))
    with pytest.raises(GovernanceError):
        validate_governance_workspace_against_authorities(
            attacked, auth, expected_workspace_hash=original
        )


def test_stale_replay_and_optimistic_concurrency_fail_closed() -> None:
    auth = authority()
    current = [auth]
    workspace = GovernanceWorkspace.initialize(auth, lambda: current[0])
    proposal = workspace.create_proposal(
        expected_workspace_revision=0, **proposal_arguments(auth)
    )
    with pytest.raises(GovernanceError) as caught:
        workspace.submit_proposal(
            proposal["proposal_id"], expected_workspace_revision=0
        )
    assert caught.value.code == GovernanceErrorCode.CONCURRENCY_CONFLICT
    current[0] = stale(auth)
    with pytest.raises(GovernanceError) as caught:
        workspace.submit_proposal(
            proposal["proposal_id"], expected_workspace_revision=1
        )
    assert caught.value.code == GovernanceErrorCode.STALE_DIAGNOSTIC_BINDING
    current[0] = auth
    workspace.submit_proposal(proposal["proposal_id"], expected_workspace_revision=1)
    with pytest.raises(GovernanceError) as caught:
        workspace.submit_proposal(
            proposal["proposal_id"], expected_workspace_revision=2
        )
    assert caught.value.code == GovernanceErrorCode.REPLAY_DETECTED
