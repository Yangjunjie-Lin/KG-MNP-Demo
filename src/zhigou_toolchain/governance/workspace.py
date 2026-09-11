"""Historical governance event reconstruction; no filesystem store."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from zhigou_toolchain.modeling.canonical_json import semantic_hash

from .amendment_request import build_approved_amendment_request
from .authority_binding import (
    GovernanceAuthority,
    _require_verified_production_authority,
)
from .contracts import validate_governance_contract
from .errors import GovernanceError, GovernanceErrorCode
from .event_log import build_event
from .identity import governance_urn
from .proposal import create_resolution_proposal
from .review import build_review_decision
from .state_machine import require_transition
from .validator import (
    validate_governance_workspace_against_authorities,
    workspace_semantic_content,
)


def _finalize(value: dict[str, Any]) -> dict[str, Any]:
    value["workspace_revision"] = len(value["events"])
    value["head_event_hash"] = (
        value["events"][-1]["event_id"] if value["events"] else "GENESIS"
    )
    value["workspace_hash"] = semantic_hash(workspace_semantic_content(value))
    validate_governance_contract("governance-workspace", value)
    return value


def _workspace_value(authority: GovernanceAuthority) -> dict[str, Any]:
    binding = authority.binding
    value = {
        "contract_version": "1.0",
        "workspace_id": governance_urn(
            "governance-workspace", binding, authority.authority_type
        ),
        "authority_binding": binding,
        "events": [],
        "workspace_revision": 0,
        "head_event_hash": "GENESIS",
        "workspace_hash": "0" * 64,
        "status": "GOVERNANCE_WORKSPACE_ACTIVE",
    }
    return _finalize(value)


def new_workspace(authority: GovernanceAuthority) -> dict[str, Any]:
    authority = _require_verified_production_authority(authority)
    return _workspace_value(authority)


@dataclass
class GovernanceWorkspace:
    value: dict[str, Any]
    current_authority: Callable[[], GovernanceAuthority]

    @classmethod
    def initialize(
        cls,
        authority: GovernanceAuthority,
        current_authority: Callable[[], GovernanceAuthority] | None = None,
    ) -> GovernanceWorkspace:
        authority = _require_verified_production_authority(authority)
        supplied_current = current_authority or (lambda: authority)
        return cls(
            _workspace_value(authority),
            lambda: _require_verified_production_authority(supplied_current()),
        )

    def reconstruct(self) -> dict[str, Any]:
        authority = self._require_current_authority_mode()
        return validate_governance_workspace_against_authorities(
            self.value, authority
        )

    def _require_current_authority_mode(self) -> GovernanceAuthority:
        authority = _require_verified_production_authority(self.current_authority())
        mode = self.value.get("authority_binding", {}).get("authority_type")
        if mode != "PRODUCTION_EXACT_PHASE03":
            raise GovernanceError(GovernanceErrorCode.AUTHORITY_MISMATCH)
        return authority

    def _current(
        self, expected_workspace_revision: int, expected_head_hash: str | None
    ) -> GovernanceAuthority:
        if expected_workspace_revision != self.value["workspace_revision"]:
            raise GovernanceError(GovernanceErrorCode.CONCURRENCY_CONFLICT)
        if (
            expected_head_hash is not None
            and expected_head_hash != self.value["head_event_hash"]
        ):
            raise GovernanceError(GovernanceErrorCode.CONCURRENCY_CONFLICT)
        authority = self._require_current_authority_mode()
        authority.assert_same_current_authority(self.value["authority_binding"])
        self.reconstruct()
        return authority

    def _append(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        event = build_event(
            sequence=len(self.value["events"]) + 1,
            previous_event_hash=self.value["head_event_hash"],
            event_type=event_type,
            payload=payload,
            observed_at=observed_at,
        )
        self.value["events"].append(event)
        _finalize(self.value)
        return event

    def create_proposal(
        self,
        *,
        expected_workspace_revision: int,
        expected_head_hash: str | None = None,
        observed_at: str | None = None,
        **arguments: Any,
    ) -> dict[str, Any]:
        authority = self._current(expected_workspace_revision, expected_head_hash)
        proposal = create_resolution_proposal(
            authority=authority,
            workspace_id=self.value["workspace_id"],
            sequence=len(self.value["events"]) + 1,
            previous_event_hash=self.value["head_event_hash"],
            **arguments,
        )
        self._append("ProposalCreated", proposal, observed_at)
        self.reconstruct()
        return deepcopy(proposal)

    def submit_proposal(
        self,
        proposal_id: str,
        *,
        expected_workspace_revision: int,
        expected_head_hash: str | None = None,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        self._current(expected_workspace_revision, expected_head_hash)
        state = self.reconstruct()
        proposal = next(
            (p for p in state["proposals"] if p["proposal_id"] == proposal_id), None
        )
        if proposal is None:
            raise GovernanceError(
                GovernanceErrorCode.INVALID_REQUEST, "unknown proposal"
            )
        if proposal["status"] == "SUBMITTED":
            raise GovernanceError(GovernanceErrorCode.REPLAY_DETECTED)
        require_transition(proposal["status"], "SUBMITTED")
        self._append(
            "ProposalSubmitted",
            {
                "proposal_id": proposal_id,
                "proposal_revision": proposal["proposal_revision"],
                "resulting_status": "SUBMITTED",
            },
            observed_at,
        )
        return next(
            p
            for p in self.reconstruct()["proposals"]
            if p["proposal_id"] == proposal_id
        )

    def review_proposal(
        self,
        proposal_id: str,
        *,
        decision: str,
        review_note: str,
        reviewed_by_label: str,
        explicit_human_action: bool,
        expected_workspace_revision: int,
        expected_head_hash: str | None = None,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        self._current(expected_workspace_revision, expected_head_hash)
        state = self.reconstruct()
        proposal = next(
            (p for p in state["proposals"] if p["proposal_id"] == proposal_id), None
        )
        if proposal is None:
            raise GovernanceError(
                GovernanceErrorCode.INVALID_REQUEST, "unknown proposal"
            )
        if any(
            item["proposal_id"] == proposal_id for item in state["review_decisions"]
        ):
            raise GovernanceError(GovernanceErrorCode.REPLAY_DETECTED)
        review, target, event_type = build_review_decision(
            workspace_id=self.value["workspace_id"],
            sequence=len(self.value["events"]) + 1,
            previous_event_hash=self.value["head_event_hash"],
            proposal=proposal,
            decision=decision,
            review_note=review_note,
            reviewed_by_label=reviewed_by_label,
            explicit_human_action=explicit_human_action,
        )
        require_transition(proposal["status"], target)
        review_event = self._append(event_type, review, observed_at)
        result: dict[str, Any] = {"review_decision": review, "amendment_request": None}
        if decision == "APPROVE_FOR_AMENDMENT":
            amendment = build_approved_amendment_request(
                proposal={**proposal, "status": target},
                decision=review,
                review_event_id=review_event["event_id"],
            )
            self._append("AmendmentRequestProduced", amendment, observed_at)
            result["amendment_request"] = amendment
        self.reconstruct()
        return result
