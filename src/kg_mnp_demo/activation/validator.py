"""Independent event, state, pointer, and authority reconstruction for Phase 06."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes, semantic_hash

from .contracts import validate_activation_contract
from .errors import ActivationError, ActivationErrorCode
from .event_log import build_activation_event, validate_activation_event_chain
from .pointer import (
    build_current_publication_pointer,
    validate_current_publication_pointer,
)
from .proposal import create_activation_proposal
from .registry import (
    authority_binding_hash,
    authority_flags,
    base_target,
    eligible_targets,
    registry_semantic_content,
    resolve_authority_target,
    target_binding_hash,
    target_descriptor,
)
from .review import build_activation_review_decision
from .state_machine import require_transition


def _equal(left: Any, right: Any) -> bool:
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def _proposal_target(proposal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "publication_id": proposal["target_publication_id"],
        "publication_semantic_hash": proposal["target_publication_semantic_hash"],
        "repository_id": proposal["target_repository_id"],
        "repository_semantic_hash": proposal["target_repository_semantic_hash"],
        "publication_attestation_sha256": proposal[
            "target_publication_attestation_sha256"
        ],
        "lineage_source_type": proposal["target_lineage_source_type"],
        "lineage_source_attestation_sha256": proposal[
            "target_lineage_source_attestation_sha256"
        ],
    }


def _pointer_target(pointer: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "publication_id": pointer["active_publication_id"],
        "publication_semantic_hash": pointer["active_publication_semantic_hash"],
        "repository_id": pointer["active_repository_id"],
        "repository_semantic_hash": pointer["active_repository_semantic_hash"],
        "publication_attestation_sha256": pointer[
            "active_publication_attestation_sha256"
        ],
        "lineage_source_type": pointer["lineage_source_type"],
        "lineage_source_attestation_sha256": pointer[
            "lineage_source_attestation_sha256"
        ],
    }


def _execution_identity_content(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value) for key, value in payload.items() if key != "execution_id"
    }


def _expected_execution_id(payload: Mapping[str, Any], *, test_only: bool) -> str:
    prefix = (
        "urn:kg-mnp:test-fixture:phase06:activation-execution:"
        if test_only
        else "urn:kg-mnp:activation-execution:"
    )
    return prefix + semantic_hash(_execution_identity_content(payload))


def _target_from_authority(
    authority: object, proposal: Mapping[str, Any]
) -> dict[str, Any]:
    target = resolve_authority_target(authority, str(proposal["target_publication_id"]))
    descriptor = target_descriptor(target)
    if (
        not _equal(descriptor, _proposal_target(proposal))
        or target_binding_hash(authority, descriptor["publication_id"])
        != proposal["target_authority_binding_hash"]
    ):
        raise ValueError("proposal target differs from verified authority")
    return descriptor


def _bootstrap(
    registry: Mapping[str, Any], authority: object
) -> tuple[dict[str, Any], dict[str, Any]]:
    test_only, production = authority_flags(authority)
    binding_hash = authority_binding_hash(authority)
    target = target_descriptor(base_target(authority))
    prefix = (
        "urn:kg-mnp:test-fixture:phase06:activation-registry:"
        if test_only
        else "urn:kg-mnp:activation-registry:"
    )
    expected_registry_id = prefix + semantic_hash(
        {"authority_binding_hash": binding_hash, "base_publication": target}
    )
    if (
        registry["registry_id"] != expected_registry_id
        or registry["authority_binding_hash"] != binding_hash
        or registry["test_only"] is not test_only
        or registry["production_authority"] is not production
        or registry["semantic_authority"] is not False
        or registry["deployment_governance_only"] is not True
        or registry["status"] != "ACTIVATION_REGISTRY_ACTIVE"
    ):
        raise ValueError("registry authority/bootstrap binding mismatch")
    pointer = build_current_publication_pointer(
        registry_id=expected_registry_id,
        generation=0,
        target=target,
        previous_pointer_hash="GENESIS",
        test_only=test_only,
    )
    if not _equal(registry["bootstrap_pointer"], pointer):
        raise ValueError("bootstrap pointer mismatch")
    event = registry["events"][0]
    if event["event_type"] != "RegistryBootstrapped":
        raise ValueError("registry does not begin with bootstrap")
    expected_event = build_activation_event(
        sequence=1,
        previous_event_hash="GENESIS",
        event_type="RegistryBootstrapped",
        payload={
            "bootstrap_pointer": pointer,
            "bootstrap_authority_binding_hash": binding_hash,
            "bootstrap_status": "BOOTSTRAP_CURRENT_REFERENCE",
        },
        test_only=test_only,
        production_authority=production,
        observed_at=event["observed_at"],
    )
    if not _equal(event, expected_event):
        raise ValueError("bootstrap event mismatch")
    return pointer, target


def validate_activation_registry_against_authorities(
    registry: Mapping[str, Any],
    authority: object,
    *,
    current_pointer: Mapping[str, Any] | None = None,
    expected_registry_hash: str | None = None,
    expected_head_event_hash: str | None = None,
) -> dict[str, Any]:
    """Rebuild the complete control state and bind it to verified publications.

    ``expected_registry_hash`` and ``expected_head_event_hash`` are the trusted
    external anchors needed to reject a self-consistent full-history rehash.
    """

    value = deepcopy(dict(registry))
    try:
        validate_activation_contract("activation-registry", value)
        events = value["events"]
        if not events:
            raise ValueError("activation registry has no bootstrap event")
        head = validate_activation_event_chain(events)
        if (
            value["registry_revision"] != len(events)
            or value["head_event_hash"] != head
        ):
            raise ValueError("registry revision/head mismatch")
        digest = semantic_hash(registry_semantic_content(value))
        if value["registry_hash"] != digest:
            raise ValueError("registry hash mismatch")
        if expected_registry_hash is not None and digest != expected_registry_hash:
            raise ValueError("registry differs from trusted registry anchor")
        if expected_head_event_hash is not None and head != expected_head_event_hash:
            raise ValueError("registry differs from trusted head anchor")

        pointer, _base = _bootstrap(value, authority)
        test_only = bool(value["test_only"])
        production = bool(value["production_authority"])
        candidate_ids = {
            target_descriptor(item)["publication_id"]
            for item in eligible_targets(authority)
        }
        proposals: dict[str, dict[str, Any]] = {}
        decisions: dict[str, dict[str, Any]] = {}
        executed: dict[str, dict[str, Any]] = {}
        pointer_history: list[dict[str, Any]] = [deepcopy(pointer)]
        activation_cycles = 0
        rollback_cycles = 0

        for event in events[1:]:
            if (
                event["test_only"] is not test_only
                or event["production_authority"] is not production
            ):
                raise ValueError("event authority mode mismatch")
            payload = event["payload"]
            event_type = event["event_type"]
            if event_type == "ActivationProposalCreated":
                supplied = deepcopy(dict(payload))
                target = _target_from_authority(authority, supplied)
                if (
                    supplied["base_pointer_hash"] != pointer["pointer_hash"]
                    or supplied["base_generation"] != pointer["generation"]
                    or target["publication_id"] == pointer["active_publication_id"]
                ):
                    raise ValueError("proposal base/target mismatch")
                historical_ids = {
                    item["active_publication_id"] for item in pointer_history
                }
                if (
                    supplied["activation_kind"] == "ACTIVATE_NEW_VERIFIED_PUBLICATION"
                    and target["publication_id"] not in candidate_ids
                ):
                    raise ValueError("activation target is not Phase05 eligible")
                if (
                    supplied["activation_kind"]
                    == "ROLLBACK_TO_PRIOR_VERIFIED_PUBLICATION"
                    and target["publication_id"] not in historical_ids
                ):
                    raise ValueError("rollback target is absent from history")
                expected = create_activation_proposal(
                    activation_kind=supplied["activation_kind"],
                    target=target,
                    base_pointer_hash=supplied["base_pointer_hash"],
                    base_generation=supplied["base_generation"],
                    target_authority_binding_hash=target_binding_hash(
                        authority, target["publication_id"]
                    ),
                    rationale=supplied["rationale"],
                    created_by_label=supplied["created_by_label"],
                    explicit_human_intent=supplied["explicit_human_intent"],
                    test_only=test_only,
                    production_authority=production,
                )
                if not _equal(supplied, expected):
                    raise ValueError("proposal identity mismatch")
                proposal_id = expected["activation_proposal_id"]
                if proposal_id in proposals:
                    raise ValueError("duplicate activation proposal")
                proposals[proposal_id] = expected
            elif event_type == "ActivationProposalSubmitted":
                if set(payload) != {"activation_proposal_id", "resulting_status"}:
                    raise ValueError("submission payload field mismatch")
                proposal = proposals[payload["activation_proposal_id"]]
                if payload["resulting_status"] != "SUBMITTED":
                    raise ValueError("submission result mismatch")
                require_transition(proposal["status"], "SUBMITTED")
                proposal["status"] = "SUBMITTED"
            elif event_type in {
                "ActivationReviewApproved",
                "ActivationReviewRejected",
                "ActivationReviewDeferred",
            }:
                supplied = deepcopy(dict(payload))
                proposal = proposals[supplied["activation_proposal_id"]]
                expected, target_status, expected_event_type = (
                    build_activation_review_decision(
                        proposal=proposal,
                        decision=supplied["decision"],
                        reviewed_by_label=supplied["reviewed_by_label"],
                        review_note=supplied["review_note"],
                        explicit_human_action=supplied["explicit_human_action"],
                    )
                )
                if expected_event_type != event_type or not _equal(supplied, expected):
                    raise ValueError("activation review identity mismatch")
                require_transition(proposal["status"], target_status)
                proposal["status"] = target_status
                decision_id = expected["activation_review_decision_id"]
                if decision_id in decisions or any(
                    item["activation_proposal_id"] == expected["activation_proposal_id"]
                    for item in decisions.values()
                ):
                    raise ValueError("duplicate activation review")
                decisions[decision_id] = expected
            elif event_type in {"ActivationApplied", "RollbackApplied"}:
                required = {
                    "execution_id",
                    "proposal_id",
                    "review_decision_id",
                    "old_pointer",
                    "new_pointer",
                    "verification_evidence_hashes",
                    "status",
                }
                if set(payload) != required:
                    raise ValueError("execution payload field mismatch")
                proposal = proposals[payload["proposal_id"]]
                decision = decisions[payload["review_decision_id"]]
                if (
                    proposal["status"] != "APPROVED_FOR_ACTIVATION"
                    or decision["activation_proposal_id"] != payload["proposal_id"]
                    or decision["decision"] != "APPROVE_FOR_ACTIVATION"
                    or payload["proposal_id"] in executed
                ):
                    raise ValueError("execution lacks one unused explicit approval")
                old_pointer = validate_current_publication_pointer(
                    payload["old_pointer"]
                )
                new_pointer = validate_current_publication_pointer(
                    payload["new_pointer"]
                )
                if (
                    not _equal(old_pointer, pointer)
                    or proposal["base_pointer_hash"] != old_pointer["pointer_hash"]
                    or proposal["base_generation"] != old_pointer["generation"]
                    or new_pointer["generation"] != old_pointer["generation"] + 1
                    or new_pointer["previous_pointer_hash"]
                    != old_pointer["pointer_hash"]
                    or not _equal(
                        _pointer_target(new_pointer), _proposal_target(proposal)
                    )
                ):
                    raise ValueError("execution CAS/pointer generation mismatch")
                evidence = payload["verification_evidence_hashes"]
                if set(evidence) != {
                    "publication_tree_sha256",
                    "publication_attestation_sha256",
                    "expected_repository_semantic_hash",
                    "live_repository_semantic_hash",
                }:
                    raise ValueError("execution evidence field mismatch")
                if (
                    evidence["publication_attestation_sha256"]
                    != proposal["target_publication_attestation_sha256"]
                    or evidence["expected_repository_semantic_hash"]
                    != proposal["target_repository_semantic_hash"]
                    or evidence["live_repository_semantic_hash"]
                    != proposal["target_repository_semantic_hash"]
                ):
                    raise ValueError("execution did not verify exact target")
                authority_target = resolve_authority_target(
                    authority, str(proposal["target_publication_id"])
                )
                expected_tree = getattr(
                    authority_target, "publication_tree_sha256", None
                )
                if (
                    expected_tree is not None
                    and evidence["publication_tree_sha256"] != expected_tree
                ):
                    raise ValueError("execution publication-tree evidence mismatch")
                expected_event_type = (
                    "ActivationApplied"
                    if proposal["activation_kind"]
                    == "ACTIVATE_NEW_VERIFIED_PUBLICATION"
                    else "RollbackApplied"
                )
                expected_status = (
                    "ACTIVATION_APPLIED"
                    if expected_event_type == "ActivationApplied"
                    else "ROLLBACK_APPLIED"
                )
                if (
                    event_type != expected_event_type
                    or payload["status"] != expected_status
                    or payload["execution_id"]
                    != _expected_execution_id(payload, test_only=test_only)
                ):
                    raise ValueError("execution identity/type/status mismatch")
                target = _target_from_authority(authority, proposal)
                if not _equal(target, _pointer_target(new_pointer)):
                    raise ValueError("execution target authority mismatch")
                executed[payload["proposal_id"]] = {
                    **deepcopy(dict(payload)),
                    "event_id": event["event_id"],
                    "event_hash": event["event_hash"],
                }
                pointer = new_pointer
                pointer_history.append(deepcopy(pointer))
                if event_type == "ActivationApplied":
                    activation_cycles += 1
                else:
                    rollback_cycles += 1
            else:
                raise ValueError("unsupported or repeated bootstrap event")

        if value["current_pointer_hash"] != pointer["pointer_hash"]:
            raise ValueError("registry current pointer projection mismatch")
        if current_pointer is not None:
            supplied_pointer = validate_current_publication_pointer(current_pointer)
            if not _equal(supplied_pointer, pointer):
                raise ValueError("persisted current pointer differs from registry")
    except ActivationError as exc:
        if exc.code in {
            ActivationErrorCode.REGISTRY_TAMPERED,
            ActivationErrorCode.POINTER_TAMPERED,
        }:
            raise
        raise ActivationError(
            ActivationErrorCode.REGISTRY_TAMPERED,
            "activation registry authority/state reconstruction failed",
        ) from exc
    except Exception as exc:
        raise ActivationError(
            ActivationErrorCode.REGISTRY_TAMPERED,
            "activation registry authority/state reconstruction failed",
        ) from exc

    return {
        "registry_id": value["registry_id"],
        "registry_hash": value["registry_hash"],
        "registry_revision": value["registry_revision"],
        "head_event_hash": value["head_event_hash"],
        "proposals": [deepcopy(item) for item in proposals.values()],
        "review_decisions": [deepcopy(item) for item in decisions.values()],
        "executions": [deepcopy(item) for item in executed.values()],
        "pointer_history": pointer_history,
        "current_pointer": deepcopy(pointer),
        "activation_cycles": activation_cycles,
        "rollback_cycles": rollback_cycles,
        "status": "ACTIVATION_REGISTRY_VERIFIED",
    }
