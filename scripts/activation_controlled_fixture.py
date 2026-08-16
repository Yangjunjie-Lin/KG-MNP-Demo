#!/usr/bin/env python3
"""TEST-ONLY deterministic P0 -> P1 -> P0 Phase 06 control-plane fixture."""

from __future__ import annotations

import argparse
import json
import multiprocessing
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from kg_mnp_demo.activation.attestation import (
    build_controlled_publication_attestation,
    publication_tree_sha256,
)
from kg_mnp_demo.activation.authority_binding import ControlledPhase06Authority
from kg_mnp_demo.activation.errors import ActivationError
from kg_mnp_demo.activation.execution import (
    ActivationController,
    ReadOnlyGraphDBTargetVerifier,
    TargetReverifier,
)
from kg_mnp_demo.activation.persistence import ActivationStateStore
from kg_mnp_demo.activation.resolver import ActivePublicationResolver
from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes

if __package__:
    from scripts.amendment_controlled_fixture import build_controlled_publication_pair
else:
    from amendment_controlled_fixture import (  # type: ignore[import-not-found]
        build_controlled_publication_pair,
    )


class _PackageSnapshotClient:
    """Read-only GraphDB-shaped client over already-built package snapshots."""

    def __init__(self, packages: dict[str, Path]):
        self._packages = dict(packages)

    def repository_info(self, repository_id: str) -> dict[str, str]:
        if repository_id not in self._packages:
            raise OSError("controlled repository is unavailable")
        return {"id": repository_id}

    def export_explicit_nquads(self, repository_id: str) -> bytes:
        try:
            return (
                self._packages[repository_id] / "import/knowledge-graph.nq"
            ).read_bytes()
        except (KeyError, OSError) as exc:
            raise OSError("controlled repository is unavailable") from exc


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def build_controlled_activation_fixture(output_root: Path) -> dict[str, Any]:
    """Build explicit test-only Phase05 publications and Phase06 authority."""

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    phase05, old, new = build_controlled_publication_pair(root / "phase05")
    attestations = root / "attestations"
    p0_attestation = build_controlled_publication_attestation(
        publication_manifest=old["publication_manifest"],
        graphdb_manifest=old["graphdb_manifest"],
        controlled_fixture_hash=phase05["controlled_fixture_hash"],
        publication_role="P0",
    )
    p1_attestation = build_controlled_publication_attestation(
        publication_manifest=new["publication_manifest"],
        graphdb_manifest=new["graphdb_manifest"],
        controlled_fixture_hash=phase05["controlled_fixture_hash"],
        publication_role="P1",
    )
    p0_attestation_path = attestations / "p0-controlled-attestation.json"
    p1_attestation_path = attestations / "p1-controlled-attestation.json"
    _write_json(p0_attestation_path, p0_attestation)
    _write_json(p1_attestation_path, p1_attestation)
    authority = ControlledPhase06Authority.create(
        p0_package_directory=old["publication_directory"],
        p0_manifest=old["publication_manifest"],
        p0_attestation_path=p0_attestation_path,
        p1_package_directory=new["publication_directory"],
        p1_manifest=new["publication_manifest"],
        p1_attestation_path=p1_attestation_path,
    )
    packages = {
        old["graphdb_manifest"]["repository_id"]: old["graphdb_directory"],
        new["graphdb_manifest"]["repository_id"]: new["graphdb_directory"],
    }
    return {
        "phase05_evidence": phase05,
        "old": old,
        "new": new,
        "authority": authority,
        "p0_attestation_path": p0_attestation_path,
        "p1_attestation_path": p1_attestation_path,
        "offline_verifier": ReadOnlyGraphDBTargetVerifier(
            _PackageSnapshotClient(packages)  # type: ignore[arg-type]
        ),
    }


def _proposal(
    controller: ActivationController,
    *,
    target_publication_id: str,
    activation_kind: str,
    rationale: str,
) -> dict[str, Any]:
    state = controller.status()
    return controller.create_proposal(
        target_publication_id=target_publication_id,
        activation_kind=activation_kind,
        rationale=rationale,
        created_by_label="Phase06 controlled deployment operator label",
        explicit_human_intent=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )


def _submit(controller: ActivationController, proposal_id: str) -> None:
    state = controller.status()
    controller.submit_proposal(
        proposal_id,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )


def _review(
    controller: ActivationController,
    proposal_id: str,
    *,
    decision: str,
    note: str,
) -> dict[str, Any]:
    state = controller.status()
    return controller.record_review(
        proposal_id,
        decision=decision,
        reviewed_by_label="Phase06 controlled human reviewer label",
        review_note=note,
        explicit_human_action=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )


def run_controlled_activation_workflow(
    *,
    fixture: dict[str, Any],
    state_directory: Path,
    verifier: TargetReverifier,
    checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Exercise reject/defer, activation, resolution, and governed rollback."""

    authority = fixture["authority"]
    controller = ActivationController(
        ActivationStateStore(state_directory, authority), verifier
    )
    initial_registry, initial_pointer = controller.initialize()
    p0 = authority.base_publication
    p1 = authority.activation_candidates[0]

    for decision in ("REJECT", "DEFER"):
        terminal = _proposal(
            controller,
            target_publication_id=p1.publication_id,
            activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
            rationale=f"Controlled {decision.casefold()} no-pointer-change scenario.",
        )
        _submit(controller, terminal["activation_proposal_id"])
        before = controller.status()["current_pointer"]
        _review(
            controller,
            terminal["activation_proposal_id"],
            decision=decision,
            note=f"Explicit human {decision.casefold()} deployment decision.",
        )
        if controller.status()["current_pointer"] != before:
            raise ValueError(f"{decision} changed the current publication pointer")

    activation_proposal = _proposal(
        controller,
        target_publication_id=p1.publication_id,
        activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
        rationale="Select the verified immutable controlled P1 for deployment.",
    )
    _submit(controller, activation_proposal["activation_proposal_id"])
    activation_decision = _review(
        controller,
        activation_proposal["activation_proposal_id"],
        decision="APPROVE_FOR_ACTIVATION",
        note="Explicit human approval to select controlled P1.",
    )
    before_activation = controller.status()["current_pointer"]
    activation_receipt = controller.execute(
        activation_proposal["activation_proposal_id"],
        activation_decision["activation_review_decision_id"],
        expected_generation=before_activation["generation"],
        expected_pointer_hash=before_activation["pointer_hash"],
    )
    post_activation_state = controller.status()
    resolved_p1 = ActivePublicationResolver(
        controller.store, verifier
    ).resolve_current()
    if resolved_p1["active_publication_id"] != p1.publication_id:
        raise ValueError("controlled activation did not resolve P1")
    if checkpoint is not None:
        checkpoint("after_activation")

    rollback_proposal = _proposal(
        controller,
        target_publication_id=p0.publication_id,
        activation_kind="ROLLBACK_TO_PRIOR_VERIFIED_PUBLICATION",
        rationale="Select the prior verified immutable controlled P0 again.",
    )
    _submit(controller, rollback_proposal["activation_proposal_id"])
    rollback_decision = _review(
        controller,
        rollback_proposal["activation_proposal_id"],
        decision="APPROVE_FOR_ACTIVATION",
        note="Explicit human approval to roll back selection to controlled P0.",
    )
    before_rollback = controller.status()["current_pointer"]
    rollback_receipt = controller.execute(
        rollback_proposal["activation_proposal_id"],
        rollback_decision["activation_review_decision_id"],
        expected_generation=before_rollback["generation"],
        expected_pointer_hash=before_rollback["pointer_hash"],
    )
    final_registry, final_pointer, final_state = controller.store.load()
    resolved_p0 = ActivePublicationResolver(
        controller.store, verifier
    ).resolve_current()
    if checkpoint is not None:
        checkpoint("after_rollback")
    if (
        [item["generation"] for item in final_state["pointer_history"]] != [0, 1, 2]
        or final_state["activation_cycles"] != 1
        or final_state["rollback_cycles"] != 1
        or resolved_p0["active_publication_id"] != p0.publication_id
    ):
        raise ValueError("controlled activation/rollback invariants failed")
    return {
        "initial_registry": initial_registry,
        "initial_pointer": initial_pointer,
        "activation_proposal": activation_proposal,
        "activation_review_decision": activation_decision,
        "activation_receipt": activation_receipt,
        "post_activation_state": post_activation_state,
        "resolved_p1": resolved_p1,
        "rollback_proposal": rollback_proposal,
        "rollback_review_decision": rollback_decision,
        "rollback_receipt": rollback_receipt,
        "final_registry": final_registry,
        "final_pointer": final_pointer,
        "final_state": final_state,
        "resolved_p0": resolved_p0,
        "p0_publication_tree_sha256": publication_tree_sha256(p0.package_directory),
        "p1_publication_tree_sha256": publication_tree_sha256(p1.package_directory),
        "status": "CONTROLLED_ACTIVATION_AND_ROLLBACK_VERIFIED",
    }


def run_offline_harness(output_root: Path) -> dict[str, Any]:
    fixture = build_controlled_activation_fixture(output_root)
    result = run_controlled_activation_workflow(
        fixture=fixture,
        state_directory=output_root / "state",
        verifier=fixture["offline_verifier"],
    )
    return {
        "controlled_fixture_hash": fixture["authority"].controlled_fixture_hash,
        "activation_proposal_id": result["activation_proposal"][
            "activation_proposal_id"
        ],
        "activation_review_decision_id": result["activation_review_decision"][
            "activation_review_decision_id"
        ],
        "rollback_proposal_id": result["rollback_proposal"]["activation_proposal_id"],
        "rollback_review_decision_id": result["rollback_review_decision"][
            "activation_review_decision_id"
        ],
        "generation_sequence": [0, 1, 2],
        "registry_hash": result["final_state"]["registry_hash"],
        "head_event_hash": result["final_state"]["head_event_hash"],
        "status": result["status"],
    }


def _race_worker(
    state_directory: str,
    authority: ControlledPhase06Authority,
    packages: dict[str, Path],
    proposal_id: str,
    decision_id: str,
    generation: int,
    pointer_hash: str,
    start: Any,
    results: Any,
) -> None:
    controller = ActivationController(
        ActivationStateStore(Path(state_directory), authority),
        ReadOnlyGraphDBTargetVerifier(
            _PackageSnapshotClient(packages)  # type: ignore[arg-type]
        ),
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


def run_controlled_process_race(
    *, fixture: dict[str, Any], state_directory: Path
) -> dict[str, Any]:
    """Run the required same-generation race in two spawned processes."""

    authority = fixture["authority"]
    packages = {
        fixture["old"]["graphdb_manifest"]["repository_id"]: fixture["old"][
            "graphdb_directory"
        ],
        fixture["new"]["graphdb_manifest"]["repository_id"]: fixture["new"][
            "graphdb_directory"
        ],
    }
    controller = ActivationController(
        ActivationStateStore(state_directory, authority), fixture["offline_verifier"]
    )
    controller.initialize()
    proposal = _proposal(
        controller,
        target_publication_id=authority.activation_candidates[0].publication_id,
        activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
        rationale="Controlled same-generation process race.",
    )
    _submit(controller, proposal["activation_proposal_id"])
    decision = _review(
        controller,
        proposal["activation_proposal_id"],
        decision="APPROVE_FOR_ACTIVATION",
        note="Explicit human approval before the controlled process race.",
    )
    pointer = controller.status()["current_pointer"]
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    arguments = (
        str(state_directory),
        authority,
        packages,
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
    outcomes = [results.get(timeout=60) for _ in processes]
    for process in processes:
        process.join(timeout=60)
        if process.exitcode != 0:
            raise RuntimeError("controlled activation race worker failed")
    final = controller.status()
    if (
        sorted(outcomes)
        != sorted(["ACTIVATION_APPLIED", "ACTIVATION_CONCURRENCY_CONFLICT"])
        or final["current_pointer"]["generation"] != 1
    ):
        raise ValueError("controlled cross-process CAS race invariant failed")
    return {
        "processes": 2,
        "success": outcomes.count("ACTIVATION_APPLIED"),
        "blocked": outcomes.count("ACTIVATION_CONCURRENCY_CONFLICT"),
        "outcomes": sorted(outcomes),
        "final_generation": final["current_pointer"]["generation"],
        "status": "CONTROLLED_PROCESS_RACE_VERIFIED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    if args.output_root:
        result = run_offline_harness(args.output_root)
    else:
        with TemporaryDirectory(prefix="kg-mnp-phase06-controlled-") as directory:
            result = run_offline_harness(Path(directory))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
