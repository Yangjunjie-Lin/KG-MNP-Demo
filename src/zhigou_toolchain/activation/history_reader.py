"""Read-only projections of versioned activation history, never an executor.

Recorded states are replayed against independently reconstructed publication
authorities and explicit trusted anchors. Historical READY/APPLIED labels are
data projections, not observations that an external system is deployed now.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from zhigou_toolchain.modeling.canonical_json import semantic_hash

from .attestation import publication_tree_sha256
from .contracts import validate_activation_contract
from .errors import ActivationError, ActivationErrorCode
from .registry import _finalize, target_descriptor
from .validator import validate_activation_registry_against_authorities


def build_execution_payload(
    *,
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    old_pointer: Mapping[str, Any],
    new_pointer: Mapping[str, Any],
    verification_evidence_hashes: Mapping[str, str],
    test_only: bool,
) -> dict[str, Any]:
    status = (
        "ACTIVATION_APPLIED"
        if proposal["activation_kind"] == "ACTIVATE_NEW_VERIFIED_PUBLICATION"
        else "ROLLBACK_APPLIED"
    )
    payload: dict[str, Any] = {
        "proposal_id": proposal["activation_proposal_id"],
        "review_decision_id": decision["activation_review_decision_id"],
        "old_pointer": deepcopy(dict(old_pointer)),
        "new_pointer": deepcopy(dict(new_pointer)),
        "verification_evidence_hashes": dict(verification_evidence_hashes),
        "status": status,
    }
    payload["execution_id"] = (
        "urn:kg-mnp:test-fixture:phase06:activation-execution:"
        if test_only
        else "urn:kg-mnp:activation-execution:"
    ) + semantic_hash(payload)
    return payload


def build_execution_receipt(*, execution_payload: Mapping[str, Any], proposal: Mapping[str, Any], event_id: str) -> dict[str, Any]:
    old_pointer, new_pointer = execution_payload["old_pointer"], execution_payload["new_pointer"]
    value = {
        "contract_version": "1.0", "execution_id": execution_payload["execution_id"],
        "proposal_id": execution_payload["proposal_id"], "review_decision_id": execution_payload["review_decision_id"],
        "old_pointer_hash": old_pointer["pointer_hash"], "new_pointer_hash": new_pointer["pointer_hash"],
        "old_generation": old_pointer["generation"], "new_generation": new_pointer["generation"],
        **{key: proposal[key] for key in ("target_publication_id", "target_publication_semantic_hash", "target_repository_id", "target_repository_semantic_hash", "target_publication_attestation_sha256")},
        "verification_evidence_hashes": deepcopy(dict(execution_payload["verification_evidence_hashes"])),
        "event_id": event_id, "semantic_authority": False, "deployment_governance_only": True,
        "test_only": proposal["test_only"], "production_authority": proposal["production_authority"],
        "status": execution_payload["status"],
    }
    validate_activation_contract("activation-execution-receipt", value)
    return value


def _resolved(state: dict, execution: dict, target: object) -> dict:
    pointer = state["current_pointer"]
    descriptor = target_descriptor(target)
    return {
        "contract_version": "1.0", "pointer_id": pointer["pointer_id"], "pointer_hash": pointer["pointer_hash"],
        "generation": pointer["generation"],
        **{"active_" + key: descriptor[key] for key in ("publication_id", "publication_semantic_hash", "repository_id", "repository_semantic_hash", "publication_attestation_sha256")},
        "verification_evidence_hashes": deepcopy(execution["verification_evidence_hashes"]),
        "registry_hash": state["registry_hash"], "head_event_hash": state["head_event_hash"],
        "semantic_authority": False, "deployment_selection_metadata": True, "status": "ACTIVE_PUBLICATION_READY",
    }


def reconstruct_controlled_history(registry: Mapping[str, Any], pointer: Mapping[str, Any], *, authority: object,
                                   expected_registry_hash: str, expected_head_event_hash: str) -> dict[str, Any]:
    """Read the historical rejected/deferred/P0→P1→P0 transcript, without writes.

    No trusted anchor is inferred from the supplied document. Every prefix is
    replayed by the original independent validator against the supplied *trusted*
    publication authority; callers must independently obtain that authority.
    """
    if not expected_registry_hash or not expected_head_event_hash:
        raise ActivationError(ActivationErrorCode.REGISTRY_TAMPERED, "trusted history anchors are required")
    value, final_pointer = deepcopy(dict(registry)), deepcopy(dict(pointer))
    final_state = validate_activation_registry_against_authorities(value, authority, current_pointer=final_pointer,
        expected_registry_hash=expected_registry_hash, expected_head_event_hash=expected_head_event_hash)
    if (not value["test_only"] or value["production_authority"]
            or final_state["activation_cycles"] != 1 or final_state["rollback_cycles"] != 1
            or [p["generation"] for p in final_state["pointer_history"]] != [0, 1, 2]):
        raise ActivationError(ActivationErrorCode.REGISTRY_TAMPERED, "controlled activation/rollback transcript required")
    events = value["events"]
    applied = [event for event in events if event["event_type"] in {"ActivationApplied", "RollbackApplied"}]
    if [event["event_type"] for event in applied] != ["ActivationApplied", "RollbackApplied"]:
        raise ActivationError(ActivationErrorCode.REGISTRY_TAMPERED, "activation must precede rollback")
    reviewed = [event for event in events if event["event_type"] in {"ActivationReviewRejected", "ActivationReviewDeferred"}]
    if {event["event_type"] for event in reviewed} != {"ActivationReviewRejected", "ActivationReviewDeferred"}:
        raise ActivationError(ActivationErrorCode.REGISTRY_TAMPERED, "historical reject/defer evidence required")

    def prefix(event, selected_pointer):
        partial = deepcopy(value)
        partial["events"] = deepcopy(events[:events.index(event) + 1])
        _finalize(partial, selected_pointer)
        state = validate_activation_registry_against_authorities(partial, authority, current_pointer=selected_pointer)
        return partial, state

    initial_pointer = value["bootstrap_pointer"]
    initial_registry, _initial = prefix(events[0], initial_pointer)
    _post_registry, post_state = prefix(applied[0], applied[0]["payload"]["new_pointer"])
    result = {"initial_registry": initial_registry, "initial_pointer": deepcopy(initial_pointer),
              "post_activation_state": post_state, "final_registry": value, "final_pointer": final_pointer,
              "final_state": final_state, "status": "CONTROLLED_ACTIVATION_AND_ROLLBACK_VERIFIED"}
    for label, event in zip(("activation", "rollback"), applied, strict=True):
        execution = event["payload"]
        proposal = next(e["payload"] for e in events if e["event_type"] == "ActivationProposalCreated"
                        and e["payload"]["activation_proposal_id"] == execution["proposal_id"])
        decision = next(d for d in final_state["review_decisions"] if d["activation_review_decision_id"] == execution["review_decision_id"])
        result[label + "_proposal"] = deepcopy(proposal)
        result[label + "_review_decision"] = deepcopy(decision)
        result[label + "_receipt"] = build_execution_receipt(execution_payload=execution, proposal=proposal, event_id=event["event_id"])
    p0, p1 = authority.base_publication, authority.activation_candidates[0]
    result["resolved_p1"] = _resolved(post_state, applied[0]["payload"], p1)
    result["resolved_p0"] = _resolved(final_state, applied[1]["payload"], p0)
    result["p0_publication_tree_sha256"] = publication_tree_sha256(p0.package_directory)
    result["p1_publication_tree_sha256"] = publication_tree_sha256(p1.package_directory)
    return result
