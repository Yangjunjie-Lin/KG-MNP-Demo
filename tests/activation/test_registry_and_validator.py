from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

from kg_mnp_demo.activation.attestation import publication_tree_sha256
from kg_mnp_demo.activation.errors import ActivationError, ActivationErrorCode
from kg_mnp_demo.activation.execution import ActivationController
from kg_mnp_demo.activation.persistence import ActivationStateStore
from kg_mnp_demo.activation.registry import ActivationRegistry, new_activation_registry
from kg_mnp_demo.activation.validator import (
    validate_activation_registry_against_authorities,
)
from kg_mnp_demo.modeling.canonical_json import semantic_hash

from ._helpers import FakeAuthority, FakeVerifier, create_approved_proposal


def _controller(tmp_path):
    authority = FakeAuthority()
    controller = ActivationController(
        ActivationStateStore(tmp_path / "state", authority), FakeVerifier()
    )
    controller.initialize()
    return authority, controller


def test_bootstrap_is_generation_zero_not_activation(tmp_path) -> None:
    authority, controller = _controller(tmp_path)
    registry, pointer, state = controller.store.load()
    assert pointer["generation"] == 0
    assert pointer["active_publication_id"] == authority.base_publication.publication_id
    assert [event["event_type"] for event in registry["events"]] == [
        "RegistryBootstrapped"
    ]
    assert state["activation_cycles"] == state["rollback_cycles"] == 0


def test_runtime_timestamp_is_excluded_from_registry_identity() -> None:
    first, _ = new_activation_registry(
        FakeAuthority(), observed_at="2026-08-16T01:00:00Z"
    )
    second, _ = new_activation_registry(
        FakeAuthority(), observed_at="2026-08-16T02:00:00Z"
    )
    assert first["events"][0]["event_id"] == second["events"][0]["event_id"]
    assert first["registry_hash"] == second["registry_hash"]


@pytest.mark.parametrize(
    ("decision", "event_type"),
    [("REJECT", "ActivationReviewRejected"), ("DEFER", "ActivationReviewDeferred")],
)
def test_reject_and_defer_never_change_pointer(tmp_path, decision, event_type) -> None:
    authority, controller = _controller(tmp_path)
    initial = controller.status()["current_pointer"]
    state = controller.status()
    proposal = controller.create_proposal(
        target_publication_id=authority.activation_candidates[0].publication_id,
        activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
        rationale="Controlled proposal for a terminal review outcome.",
        created_by_label="operator-label",
        explicit_human_intent=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    state = controller.status()
    controller.submit_proposal(
        proposal["activation_proposal_id"],
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    state = controller.status()
    controller.record_review(
        proposal["activation_proposal_id"],
        decision=decision,
        reviewed_by_label="reviewer-label",
        review_note="Explicit human terminal decision.",
        explicit_human_action=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    registry, pointer, reconstructed = controller.store.load()
    assert pointer == initial
    assert reconstructed["activation_cycles"] == 0
    assert registry["events"][-1]["event_type"] == event_type


def test_activation_then_governed_rollback_reconstructs_generations(tmp_path) -> None:
    authority, controller = _controller(tmp_path)
    proposal, decision = create_approved_proposal(controller, authority)
    pointer = controller.status()["current_pointer"]
    activation = controller.execute(
        proposal["activation_proposal_id"],
        decision["activation_review_decision_id"],
        expected_generation=pointer["generation"],
        expected_pointer_hash=pointer["pointer_hash"],
    )
    assert activation["status"] == "ACTIVATION_APPLIED"
    assert activation["new_generation"] == 1

    state = controller.status()
    rollback = controller.propose_rollback(
        target_publication_id=authority.base_publication.publication_id,
        rationale="Explicitly select the verified immutable P0 again.",
        created_by_label="operator-label",
        explicit_human_intent=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    state = controller.status()
    controller.submit_proposal(
        rollback["activation_proposal_id"],
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    state = controller.status()
    rollback_decision = controller.record_review(
        rollback["activation_proposal_id"],
        decision="APPROVE_FOR_ACTIVATION",
        reviewed_by_label="reviewer-label",
        review_note="Explicit human rollback selection approval.",
        explicit_human_action=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    pointer = controller.status()["current_pointer"]
    receipt = controller.execute(
        rollback["activation_proposal_id"],
        rollback_decision["activation_review_decision_id"],
        expected_generation=pointer["generation"],
        expected_pointer_hash=pointer["pointer_hash"],
    )
    final = controller.status()
    assert receipt["status"] == "ROLLBACK_APPLIED"
    assert [item["generation"] for item in final["pointer_history"]] == [0, 1, 2]
    assert final["current_pointer"]["active_publication_id"] == (
        authority.base_publication.publication_id
    )
    assert final["activation_cycles"] == final["rollback_cycles"] == 1


def test_registry_anchor_rejects_self_consistent_full_rehash(tmp_path) -> None:
    authority = FakeAuthority()
    trusted = ActivationRegistry.initialize(authority)
    rewritten = ActivationRegistry.initialize(authority)
    for workspace, rationale in (
        (trusted, "Trusted human deployment rationale."),
        (rewritten, "Attacker-rewritten but self-consistent rationale."),
    ):
        workspace.create_proposal(
            target_publication_id=authority.activation_candidates[0].publication_id,
            activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
            rationale=rationale,
            created_by_label="operator-label",
            explicit_human_intent=True,
            expected_registry_revision=workspace.value["registry_revision"],
            expected_head_event_hash=workspace.value["head_event_hash"],
        )
        workspace.reconstruct()
    # Both histories independently pass all self hashes and authority checks;
    # only the separately trusted final head distinguishes the accepted one.
    assert rewritten.value["registry_hash"] != trusted.value["registry_hash"]
    with pytest.raises(ActivationError) as caught:
        validate_activation_registry_against_authorities(
            rewritten.value,
            authority,
            current_pointer=rewritten.current_pointer,
            expected_registry_hash=trusted.value["registry_hash"],
            expected_head_event_hash=trusted.value["head_event_hash"],
        )
    assert caught.value.code == ActivationErrorCode.REGISTRY_TAMPERED


@pytest.mark.parametrize("attack", ["insert", "delete", "reorder", "modify"])
def test_event_chain_attacks_are_rejected(tmp_path, attack) -> None:
    authority, controller = _controller(tmp_path)
    state = controller.status()
    controller.create_proposal(
        target_publication_id=authority.activation_candidates[0].publication_id,
        activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
        rationale="Create enough history for event-chain attack probes.",
        created_by_label="operator-label",
        explicit_human_intent=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    registry, pointer, _ = controller.store.load()
    attacked = deepcopy(registry)
    if attack == "insert":
        attacked["events"].append(deepcopy(attacked["events"][-1]))
    elif attack == "delete":
        attacked["events"].pop()
    elif attack == "reorder":
        attacked["events"].reverse()
    else:
        attacked["events"][-1]["payload"]["rationale"] = "modified"
    with pytest.raises(ActivationError) as caught:
        validate_activation_registry_against_authorities(
            attacked,
            authority,
            current_pointer=pointer,
        )
    assert caught.value.code == ActivationErrorCode.REGISTRY_TAMPERED


def test_unknown_rollback_target_is_rejected_before_event_append(tmp_path) -> None:
    authority, controller = _controller(tmp_path)
    state = controller.status()
    with pytest.raises(ActivationError) as caught:
        controller.propose_rollback(
            target_publication_id=authority.activation_candidates[0].publication_id,
            rationale="P1 is eligible but has never been active.",
            created_by_label="operator-label",
            explicit_human_intent=True,
            expected_registry_revision=state["registry_revision"],
            expected_head_event_hash=state["head_event_hash"],
        )
    assert caught.value.code == ActivationErrorCode.UNKNOWN_ROLLBACK_TARGET
    assert controller.status()["registry_revision"] == state["registry_revision"]


def test_submit_rejects_target_bytes_changed_after_proposal(tmp_path) -> None:
    authority = FakeAuthority()
    target = authority.activation_candidates[0]
    package = tmp_path / "publication"
    package.mkdir()
    artifact = package / "artifact.bin"
    artifact.write_bytes(b"verified bytes")
    attestation = tmp_path / "attestation.json"
    attestation.write_bytes(b"{}\n")
    object.__setattr__(target, "package_directory", package)
    object.__setattr__(target, "attestation_path", attestation)
    object.__setattr__(
        target, "publication_tree_sha256", publication_tree_sha256(package)
    )
    object.__setattr__(
        target,
        "publication_attestation_sha256",
        hashlib.sha256(attestation.read_bytes()).hexdigest(),
    )
    controller = ActivationController(
        ActivationStateStore(tmp_path / "state", authority), FakeVerifier()
    )
    controller.initialize()
    state = controller.status()
    proposal = controller.create_proposal(
        target_publication_id=target.publication_id,
        activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
        rationale="Target is intact when this proposal is created.",
        created_by_label="operator-label",
        explicit_human_intent=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    artifact.write_bytes(b"tampered bytes")
    state = controller.status()
    with pytest.raises(ActivationError) as caught:
        controller.submit_proposal(
            proposal["activation_proposal_id"],
            expected_registry_revision=state["registry_revision"],
            expected_head_event_hash=state["head_event_hash"],
        )
    assert caught.value.code == ActivationErrorCode.STALE_ACTIVATION_TARGET


def test_pointer_full_rehash_without_applied_event_is_rejected(tmp_path) -> None:
    _authority, controller = _controller(tmp_path)
    registry, pointer, _state = controller.store.load()
    attacked = deepcopy(pointer)
    attacked["active_publication_id"] = (
        "urn:kg-mnp:test-fixture:phase06:publication:fake"
    )
    attacked["pointer_hash"] = semantic_hash(
        {key: value for key, value in attacked.items() if key != "pointer_hash"}
    )
    with pytest.raises(ActivationError) as caught:
        validate_activation_registry_against_authorities(
            registry, FakeAuthority(), current_pointer=attacked
        )
    assert caught.value.code in {
        ActivationErrorCode.POINTER_TAMPERED,
        ActivationErrorCode.REGISTRY_TAMPERED,
    }
