"""Deterministic hash-chained Phase 06 activation events."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .contracts import validate_activation_contract
from .errors import ActivationError, ActivationErrorCode

EVENT_TYPES = frozenset(
    {
        "RegistryBootstrapped",
        "ActivationProposalCreated",
        "ActivationProposalSubmitted",
        "ActivationReviewApproved",
        "ActivationReviewRejected",
        "ActivationReviewDeferred",
        "ActivationApplied",
        "RollbackApplied",
    }
)


def event_identity_content(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "sequence": event["sequence"],
        "previous_event_hash": event["previous_event_hash"],
        "event_type": event["event_type"],
        "payload_hash": event["payload_hash"],
        "test_only": event["test_only"],
        "production_authority": event["production_authority"],
    }


def build_activation_event(
    *,
    sequence: int,
    previous_event_hash: str,
    event_type: str,
    payload: Mapping[str, Any],
    test_only: bool,
    production_authority: bool,
    observed_at: str | None = None,
) -> dict[str, Any]:
    if event_type not in EVENT_TYPES or sequence < 1:
        raise ActivationError(ActivationErrorCode.INVALID_ACTIVATION_REQUEST)
    value = {
        "contract_version": "1.0",
        "sequence": sequence,
        "previous_event_hash": previous_event_hash,
        "event_type": event_type,
        "payload": deepcopy(dict(payload)),
        "payload_hash": semantic_hash(payload),
        "test_only": test_only,
        "production_authority": production_authority,
        "observed_at": observed_at,
    }
    value["event_hash"] = semantic_hash(event_identity_content(value))
    value["event_id"] = (
        "urn:kg-mnp:test-fixture:phase06:activation-event:"
        if test_only
        else "urn:kg-mnp:activation-event:"
    ) + value["event_hash"]
    validate_activation_contract("activation-event", value)
    return value


def validate_activation_event_chain(events: list[Mapping[str, Any]]) -> str:
    previous = "GENESIS"
    seen: set[str] = set()
    try:
        for expected_sequence, supplied in enumerate(events, 1):
            event = dict(supplied)
            validate_activation_contract("activation-event", event)
            if (
                event["sequence"] != expected_sequence
                or event["previous_event_hash"] != previous
                or event["payload_hash"] != semantic_hash(event["payload"])
                or event["event_hash"] != semantic_hash(event_identity_content(event))
                or event["event_id"]
                != (
                    "urn:kg-mnp:test-fixture:phase06:activation-event:"
                    if event["test_only"]
                    else "urn:kg-mnp:activation-event:"
                )
                + event["event_hash"]
                or event["event_hash"] in seen
            ):
                raise ValueError("activation event chain mismatch")
            seen.add(event["event_hash"])
            previous = event["event_hash"]
    except ActivationError:
        raise
    except Exception as exc:
        raise ActivationError(
            ActivationErrorCode.REGISTRY_TAMPERED,
            "activation event insertion/deletion/reorder/modification detected",
        ) from exc
    return previous
