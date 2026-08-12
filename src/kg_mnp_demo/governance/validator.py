"""Independent event/state/authority reconstruction for governance workspaces."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from .amendment_request import build_approved_amendment_request
from .authority_binding import GovernanceAuthority
from .contracts import strict_json_file, validate_governance_contract
from .errors import GovernanceError, GovernanceErrorCode
from .event_log import validate_event_chain
from .proposal import create_resolution_proposal
from .review import build_review_decision
from .state_machine import require_transition


def workspace_semantic_content(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": value["contract_version"],
        "workspace_id": value["workspace_id"],
        "authority_binding": deepcopy(value["authority_binding"]),
        "events": deepcopy(value["events"]),
        "workspace_revision": value["workspace_revision"],
        "head_event_hash": value["head_event_hash"],
        "status": value["status"],
    }


def _value(workspace: Mapping[str, Any] | Path | str) -> dict[str, Any]:
    return (
        strict_json_file(Path(workspace))
        if isinstance(workspace, (Path, str))
        else deepcopy(dict(workspace))
    )


def validate_governance_workspace_against_authorities(
    workspace: Mapping[str, Any] | Path | str,
    authority: GovernanceAuthority,
    *,
    expected_workspace_hash: str | None = None,
) -> dict[str, Any]:
    """Reconstruct every identity and transition, then bind every target to Phase03."""

    value = _value(workspace)
    try:
        validate_governance_contract("governance-workspace", value)
        for event in value["events"]:
            validate_governance_contract("governance-event", event)
        authority.assert_same_current_authority(value["authority_binding"])
        expected_workspace_id = "urn:kg-mnp:governance-workspace:" + semantic_hash(
            authority.binding
        )
        if value["workspace_id"] != expected_workspace_id:
            raise ValueError("workspace identity mismatch")
        head = validate_event_chain(value["events"])
        if (
            value["workspace_revision"] != len(value["events"])
            or value["head_event_hash"] != head
        ):
            raise ValueError("workspace revision/head mismatch")
        digest = semantic_hash(workspace_semantic_content(value))
        if value["workspace_hash"] != digest:
            raise ValueError("workspace hash mismatch")
        if expected_workspace_hash is not None and digest != expected_workspace_hash:
            raise ValueError("workspace does not match trusted head anchor")

        proposals: dict[str, dict[str, Any]] = {}
        decisions: dict[str, dict[str, Any]] = {}
        amendments: dict[str, dict[str, Any]] = {}
        last_review_event: dict[str, str] = {}
        for event in value["events"]:
            payload = event["payload"]
            event_type = event["event_type"]
            if event_type == "ProposalCreated":
                supplied = deepcopy(payload)
                expected = create_resolution_proposal(
                    authority=authority,
                    workspace_id=value["workspace_id"],
                    sequence=event["sequence"],
                    previous_event_hash=event["previous_event_hash"],
                    target_diagnostic_id=supplied["target_diagnostic_id"],
                    target_diagnostic_basis_hash=supplied[
                        "target_diagnostic_basis_hash"
                    ],
                    proposal_type=supplied["proposal_type"],
                    proposed_payload=supplied["proposed_payload"],
                    rationale=supplied["rationale"],
                    created_by_label=supplied["created_by_label"],
                    proposal_revision=supplied["proposal_revision"],
                )
                if canonical_json_bytes(supplied) != canonical_json_bytes(expected):
                    raise ValueError("proposal identity/binding mismatch")
                if expected["proposal_id"] in proposals:
                    raise ValueError("duplicate proposal")
                proposals[expected["proposal_id"]] = expected
            elif event_type == "ProposalSubmitted":
                if (
                    set(payload)
                    != {"proposal_id", "proposal_revision", "resulting_status"}
                    or payload["resulting_status"] != "SUBMITTED"
                ):
                    raise ValueError("invalid submission event")
                proposal = proposals[payload["proposal_id"]]
                if payload["proposal_revision"] != proposal["proposal_revision"]:
                    raise ValueError("proposal revision mismatch")
                require_transition(proposal["status"], "SUBMITTED")
                proposal["status"] = "SUBMITTED"
            elif event_type in {"ReviewApproved", "ReviewRejected", "ReviewDeferred"}:
                supplied = deepcopy(payload)
                proposal = proposals[supplied["proposal_id"]]
                expected, target, expected_event_type = build_review_decision(
                    workspace_id=value["workspace_id"],
                    sequence=event["sequence"],
                    previous_event_hash=event["previous_event_hash"],
                    proposal=proposal,
                    decision=supplied["decision"],
                    review_note=supplied["review_note"],
                    reviewed_by_label=supplied["reviewed_by_label"],
                    explicit_human_action=supplied["explicit_human_action"],
                )
                if expected_event_type != event_type or canonical_json_bytes(
                    supplied
                ) != canonical_json_bytes(expected):
                    raise ValueError("review identity/event mismatch")
                require_transition(proposal["status"], target)
                proposal["status"] = target
                decisions[expected["review_decision_id"]] = expected
                last_review_event[expected["review_decision_id"]] = event["event_id"]
            elif event_type == "AmendmentRequestProduced":
                supplied = deepcopy(payload)
                decision = decisions[supplied["review_decision_id"]]
                proposal = proposals[decision["proposal_id"]]
                expected = build_approved_amendment_request(
                    proposal=proposal,
                    decision=decision,
                    review_event_id=last_review_event[decision["review_decision_id"]],
                )
                if canonical_json_bytes(supplied) != canonical_json_bytes(expected):
                    raise ValueError("amendment request identity mismatch")
                if expected["amendment_request_id"] in amendments:
                    raise ValueError("duplicate amendment request")
                amendments[expected["amendment_request_id"]] = expected
            else:
                raise ValueError("unsupported event type")
        approved = sum(
            p["status"] == "APPROVED_FOR_AMENDMENT" for p in proposals.values()
        )
        if approved != len(amendments):
            raise ValueError("approved proposal/amendment request mismatch")
    except GovernanceError:
        raise
    except Exception as exc:
        raise GovernanceError(
            GovernanceErrorCode.WORKSPACE_TAMPERED,
            "governance workspace authority reconstruction failed",
        ) from exc
    return {
        "workspace_hash": value["workspace_hash"],
        "workspace_revision": value["workspace_revision"],
        "head_event_hash": value["head_event_hash"],
        "proposals": list(proposals.values()),
        "review_decisions": list(decisions.values()),
        "approved_amendment_requests": list(amendments.values()),
        "status": "GOVERNANCE_WORKSPACE_VERIFIED",
    }
