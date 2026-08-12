"""Canonical append-only governance event hash chain."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .contracts import validate_governance_contract
from .errors import GovernanceError, GovernanceErrorCode

EVENT_TYPES = frozenset(
    {
        "ProposalCreated",
        "ProposalSubmitted",
        "ReviewApproved",
        "ReviewRejected",
        "ReviewDeferred",
        "AmendmentRequestProduced",
    }
)


def event_identity_content(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "sequence": event["sequence"],
        "previous_event_hash": event["previous_event_hash"],
        "event_type": event["event_type"],
        "payload_hash": event["payload_hash"],
    }


def build_event(
    *,
    sequence: int,
    previous_event_hash: str,
    event_type: str,
    payload: Mapping[str, Any],
    observed_at: str | None = None,
) -> dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise GovernanceError(GovernanceErrorCode.INVALID_REQUEST, "unknown event type")
    event = {
        "contract_version": "1.0",
        "sequence": sequence,
        "previous_event_hash": previous_event_hash,
        "event_type": event_type,
        "payload": deepcopy(dict(payload)),
        "payload_hash": semantic_hash(payload),
        "observed_at": observed_at,
    }
    event["event_id"] = semantic_hash(event_identity_content(event))
    validate_governance_contract("governance-event", event)
    return event


def validate_event_chain(events: list[Mapping[str, Any]]) -> str:
    previous = "GENESIS"
    for sequence, event in enumerate(events, start=1):
        try:
            validate_governance_contract("governance-event", event)
            if (
                event["sequence"] != sequence
                or event["previous_event_hash"] != previous
            ):
                raise ValueError("event sequence/previous hash mismatch")
            if event["payload_hash"] != semantic_hash(event["payload"]):
                raise ValueError("event payload hash mismatch")
            if event["event_id"] != semantic_hash(event_identity_content(event)):
                raise ValueError("event identity mismatch")
        except Exception as exc:
            raise GovernanceError(
                GovernanceErrorCode.WORKSPACE_TAMPERED,
                "governance event chain reconstruction failed",
            ) from exc
        previous = str(event["event_id"])
    return previous
