from __future__ import annotations

import hashlib
import multiprocessing
from pathlib import Path

import pytest

from kg_mnp_demo.activation.errors import ActivationError, ActivationErrorCode
from kg_mnp_demo.activation.execution import ActivationController
from kg_mnp_demo.activation.persistence import ActivationStateStore
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

from ._helpers import FakeAuthority, FakeVerifier, create_approved_proposal


def _race_worker(
    state_directory: str,
    proposal_id: str,
    decision_id: str,
    generation: int,
    pointer_hash: str,
    start,
    results,
) -> None:
    controller = ActivationController(
        ActivationStateStore(Path(state_directory), FakeAuthority()), FakeVerifier()
    )
    start.wait()
    try:
        receipt = controller.execute(
            proposal_id,
            decision_id,
            expected_generation=generation,
            expected_pointer_hash=pointer_hash,
        )
    except ActivationError as exc:
        results.put(exc.code.value)
    else:
        results.put(receipt["status"])


def test_real_multiprocessing_same_generation_race_has_one_winner(tmp_path) -> None:
    authority = FakeAuthority()
    state_directory = tmp_path / "race-state"
    controller = ActivationController(
        ActivationStateStore(state_directory, authority), FakeVerifier()
    )
    controller.initialize()
    proposal, decision = create_approved_proposal(controller, authority)
    pointer = controller.status()["current_pointer"]

    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    arguments = (
        str(state_directory),
        proposal["activation_proposal_id"],
        decision["activation_review_decision_id"],
        pointer["generation"],
        pointer["pointer_hash"],
        start,
        results,
    )
    processes = [context.Process(target=_race_worker, args=arguments) for _ in range(2)]
    for process in processes:
        process.start()
    start.set()
    outcomes = [results.get(timeout=30) for _ in processes]
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0
    assert sorted(outcomes) == sorted(
        ["ACTIVATION_APPLIED", "ACTIVATION_CONCURRENCY_CONFLICT"]
    )
    final = controller.status()
    assert final["current_pointer"]["generation"] == 1
    assert final["activation_cycles"] == 1


def test_prepared_pair_is_fail_closed_for_reader_and_recoverable_for_mutator(
    tmp_path,
) -> None:
    authority = FakeAuthority()
    store = ActivationStateStore(tmp_path / "state", authority)
    store.initialize()
    registry, pointer, _state = store.load()
    registry_bytes = canonical_json_bytes(registry) + b"\n"
    pointer_bytes = canonical_json_bytes(pointer) + b"\n"
    transaction = {
        "contract_version": "1.0",
        "registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
        "pointer_sha256": hashlib.sha256(pointer_bytes).hexdigest(),
        "registry": registry,
        "pointer": pointer,
        "status": "PREPARED",
    }
    store.transaction_path.write_bytes(canonical_json_bytes(transaction) + b"\n")
    with pytest.raises(ActivationError) as caught:
        store.load()
    assert caught.value.code == ActivationErrorCode.POINTER_TAMPERED
    recovered_registry, recovered_pointer, _ = store.load(recover=True)
    assert recovered_registry == registry
    assert recovered_pointer == pointer
    assert not store.transaction_path.exists()


def test_state_files_are_complete_canonical_documents(tmp_path) -> None:
    store = ActivationStateStore(tmp_path / "state", FakeAuthority())
    registry, pointer = store.initialize()
    assert store.registry_path.read_bytes() == canonical_json_bytes(registry) + b"\n"
    assert store.pointer_path.read_bytes() == canonical_json_bytes(pointer) + b"\n"
    assert not store.transaction_path.exists()


def test_state_directory_rejects_parent_traversal(tmp_path) -> None:
    with pytest.raises(ActivationError) as caught:
        ActivationStateStore(tmp_path / ".." / "escape", FakeAuthority())
    assert caught.value.code == ActivationErrorCode.PATH_REJECTED


def test_state_directory_rejects_symlink_escape(tmp_path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "linked-state"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are not available to this test user")
    with pytest.raises(ActivationError) as caught:
        ActivationStateStore(link, FakeAuthority())
    assert caught.value.code == ActivationErrorCode.PATH_REJECTED
