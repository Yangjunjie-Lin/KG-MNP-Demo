from __future__ import annotations

import hashlib
import inspect

import pytest

from kg_mnp_demo.activation.attestation import publication_tree_sha256
from kg_mnp_demo.activation.errors import ActivationError, ActivationErrorCode
from kg_mnp_demo.activation.execution import (
    ActivationController,
    ReadOnlyGraphDBTargetVerifier,
)
from kg_mnp_demo.activation.persistence import ActivationStateStore
from kg_mnp_demo.activation.resolver import ActivePublicationResolver

from ._helpers import FakeAuthority, FakeVerifier, create_approved_proposal


def _ready(tmp_path, verifier=None):
    authority = FakeAuthority()
    store = ActivationStateStore(tmp_path / "state", authority)
    controller = ActivationController(store, verifier or FakeVerifier())
    controller.initialize()
    return authority, store, controller


def test_execute_requires_explicit_human_approval(tmp_path) -> None:
    authority, _store, controller = _ready(tmp_path)
    state = controller.status()
    proposal = controller.create_proposal(
        target_publication_id=authority.activation_candidates[0].publication_id,
        activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
        rationale="Explicit deployment intent only; not approval.",
        created_by_label="operator-label",
        explicit_human_intent=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    pointer = controller.status()["current_pointer"]
    with pytest.raises(ActivationError) as caught:
        controller.execute(
            proposal["activation_proposal_id"],
            "urn:kg-mnp:test-fixture:phase06:activation-review-decision:" + "0" * 64,
            expected_generation=pointer["generation"],
            expected_pointer_hash=pointer["pointer_hash"],
        )
    assert caught.value.code == ActivationErrorCode.HUMAN_ACTIVATION_APPROVAL_REQUIRED
    assert controller.status()["current_pointer"] == pointer


def test_approval_does_not_override_target_hash_drift(tmp_path) -> None:
    authority = FakeAuthority()
    verifier = FakeVerifier(
        mismatch_repository_id=authority.activation_candidates[0].repository_id
    )
    store = ActivationStateStore(tmp_path / "state", authority)
    controller = ActivationController(store, verifier)
    controller.initialize()
    proposal, decision = create_approved_proposal(controller, authority)
    pointer = controller.status()["current_pointer"]
    with pytest.raises(ActivationError) as caught:
        controller.execute(
            proposal["activation_proposal_id"],
            decision["activation_review_decision_id"],
            expected_generation=0,
            expected_pointer_hash=pointer["pointer_hash"],
        )
    assert caught.value.code == ActivationErrorCode.TARGET_REPOSITORY_HASH_MISMATCH
    assert controller.status()["current_pointer"] == pointer


def test_execute_rechecks_publication_after_live_repository_read(tmp_path) -> None:
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

    class MutatingVerifier(FakeVerifier):
        def verify(self, supplied_target: object) -> dict[str, str]:
            result = super().verify(supplied_target)
            artifact.write_bytes(b"changed during live repository verification")
            return result

    store = ActivationStateStore(tmp_path / "state", authority)
    controller = ActivationController(store, MutatingVerifier())
    controller.initialize()
    proposal, decision = create_approved_proposal(controller, authority)
    pointer = controller.status()["current_pointer"]

    with pytest.raises(ActivationError) as caught:
        controller.execute(
            proposal["activation_proposal_id"],
            decision["activation_review_decision_id"],
            expected_generation=pointer["generation"],
            expected_pointer_hash=pointer["pointer_hash"],
        )

    assert caught.value.code == ActivationErrorCode.STALE_ACTIVATION_TARGET
    assert controller.status()["current_pointer"] == pointer


def test_replay_and_stale_cas_do_not_create_generations(tmp_path) -> None:
    authority, _store, controller = _ready(tmp_path)
    proposal, decision = create_approved_proposal(controller, authority)
    old_pointer = controller.status()["current_pointer"]
    controller.execute(
        proposal["activation_proposal_id"],
        decision["activation_review_decision_id"],
        expected_generation=0,
        expected_pointer_hash=old_pointer["pointer_hash"],
    )
    with pytest.raises(ActivationError) as stale:
        controller.execute(
            proposal["activation_proposal_id"],
            decision["activation_review_decision_id"],
            expected_generation=0,
            expected_pointer_hash=old_pointer["pointer_hash"],
        )
    assert stale.value.code == ActivationErrorCode.ACTIVATION_CONCURRENCY_CONFLICT
    current = controller.status()["current_pointer"]
    with pytest.raises(ActivationError) as replay:
        controller.execute(
            proposal["activation_proposal_id"],
            decision["activation_review_decision_id"],
            expected_generation=1,
            expected_pointer_hash=current["pointer_hash"],
        )
    assert replay.value.code == ActivationErrorCode.REPLAY_DETECTED
    assert controller.status()["current_pointer"]["generation"] == 1


def test_resolver_ready_and_fail_closed_without_fallback(tmp_path) -> None:
    authority, store, controller = _ready(tmp_path)
    initial = controller.status()
    resolver = ActivePublicationResolver(
        store,
        FakeVerifier(),
        trusted_registry_hash=initial["registry_hash"],
        trusted_head_event_hash=initial["head_event_hash"],
    )
    result = resolver.resolve_current()
    assert result["active_publication_id"] == authority.base_publication.publication_id
    assert result["generation"] == 0

    unavailable = ActivePublicationResolver(
        store,
        FakeVerifier(
            unavailable_repository_id=authority.base_publication.repository_id
        ),
        trusted_registry_hash=initial["registry_hash"],
        trusted_head_event_hash=initial["head_event_hash"],
    )
    with pytest.raises(ActivationError) as caught:
        unavailable.resolve_current()
    assert caught.value.code == ActivationErrorCode.ACTIVE_PUBLICATION_NOT_READY


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("expected_registry_hash", "f" * 64),
        ("expected_head_event_hash", "e" * 64),
        ("expected_registry_hash", ""),
    ],
)
def test_configured_resolver_anchors_cannot_be_overridden(
    tmp_path, argument, value
) -> None:
    _authority, store, controller = _ready(tmp_path)
    trusted = controller.status()
    resolver = ActivePublicationResolver(
        store,
        FakeVerifier(),
        trusted_registry_hash=trusted["registry_hash"],
        trusted_head_event_hash=trusted["head_event_hash"],
    )

    with pytest.raises(ActivationError) as caught:
        resolver.resolve_current(**{argument: value})

    assert caught.value.code == ActivationErrorCode.REGISTRY_TAMPERED


def test_resolver_reports_active_hash_mismatch_and_does_not_repair(tmp_path) -> None:
    authority = FakeAuthority()
    verifier = FakeVerifier(
        mismatch_repository_id=authority.base_publication.repository_id
    )
    store = ActivationStateStore(tmp_path / "state", authority)
    controller = ActivationController(store, FakeVerifier())
    controller.initialize()
    before_registry = store.registry_path.read_bytes()
    before_pointer = store.pointer_path.read_bytes()
    with pytest.raises(ActivationError) as caught:
        ActivePublicationResolver(store, verifier).resolve_current()
    assert caught.value.code == ActivationErrorCode.ACTIVE_REPOSITORY_MISMATCH
    assert store.registry_path.read_bytes() == before_registry
    assert store.pointer_path.read_bytes() == before_pointer


def test_resolver_does_not_silently_fallback_from_unavailable_p1(tmp_path) -> None:
    authority, store, controller = _ready(tmp_path)
    proposal, decision = create_approved_proposal(controller, authority)
    pointer = controller.status()["current_pointer"]
    controller.execute(
        proposal["activation_proposal_id"],
        decision["activation_review_decision_id"],
        expected_generation=pointer["generation"],
        expected_pointer_hash=pointer["pointer_hash"],
    )
    p1 = authority.activation_candidates[0]
    resolver = ActivePublicationResolver(
        store, FakeVerifier(unavailable_repository_id=p1.repository_id)
    )
    with pytest.raises(ActivationError) as caught:
        resolver.resolve_current()
    assert caught.value.code == ActivationErrorCode.ACTIVE_PUBLICATION_NOT_READY
    assert controller.status()["current_pointer"]["active_publication_id"] == (
        p1.publication_id
    )


def test_concrete_target_verifier_has_only_read_graphdb_dependency() -> None:
    source = inspect.getsource(ReadOnlyGraphDBTargetVerifier)
    assert "ReadOnlyGraphDBClient" in source
    assert all(
        marker not in source
        for marker in (
            "import_package",
            "SPARQL UPDATE",
            "INSERT DATA",
            "DELETE DATA",
            "delete_repository",
            "create_repository",
        )
    )
