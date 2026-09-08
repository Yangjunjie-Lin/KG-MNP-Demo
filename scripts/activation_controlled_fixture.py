"""TEST-ONLY physical reconstruction and in-memory historical event fixtures.

No persistent controller, lock, recovery, runtime server or CLI is retained.
Current production activation belongs exclusively to lifecycle/services.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any

from kg_mnp.activation.attestation import (
    build_controlled_publication_attestation,
    publication_tree_sha256,
)
from kg_mnp.activation.authority_binding import ControlledPhase06Authority
from kg_mnp.activation.history_reader import (
    build_execution_payload,
    reconstruct_controlled_history,
)
from kg_mnp.activation.pointer import build_current_publication_pointer
from kg_mnp.activation.registry import ActivationRegistry, target_descriptor
from kg_mnp.modeling.canonical_json import canonical_json_bytes

if __package__:
    from scripts.amendment_controlled_fixture import build_controlled_publication_pair
else:
    from amendment_controlled_fixture import build_controlled_publication_pair

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
    return {
        "phase05_evidence": phase05,
        "old": old,
        "new": new,
        "authority": authority,
        "p0_attestation_path": p0_attestation_path,
        "p1_attestation_path": p1_attestation_path,
    }


def build_controlled_history(*, fixture: dict[str, Any], verifier=None) -> dict[str, Any]:
    """Construct TEST-ONLY event data; independent replay must accept each prefix."""
    authority = fixture["authority"]
    if not authority.test_only or authority.production_authority:
        raise ValueError("controlled test-only authority required")
    registry = ActivationRegistry.initialize(authority)
    def proposal(target, kind, rationale):
        return registry.create_proposal(target_publication_id=target.publication_id, activation_kind=kind,
            rationale=rationale, created_by_label="Phase06 controlled deployment operator label",
            explicit_human_intent=True, expected_registry_revision=registry.value["registry_revision"],
            expected_head_event_hash=registry.value["head_event_hash"])
    def review(proposed, decision, note):
        identifier = proposed["activation_proposal_id"]
        registry.submit_proposal(identifier, expected_registry_revision=registry.value["registry_revision"],
                                 expected_head_event_hash=registry.value["head_event_hash"])
        return registry.record_review(identifier, decision=decision,
            reviewed_by_label="Phase06 controlled human reviewer label", review_note=note,
            explicit_human_action=True, expected_registry_revision=registry.value["registry_revision"],
            expected_head_event_hash=registry.value["head_event_hash"])
    p0, p1 = authority.base_publication, authority.activation_candidates[0]
    for decision in ("REJECT", "DEFER"):
        p = proposal(p1, "ACTIVATE_NEW_VERIFIED_PUBLICATION", f"Controlled {decision.casefold()} no-pointer-change scenario.")
        review(p, decision, f"Explicit human {decision.casefold()} deployment decision.")
    for target, kind, rationale, note in (
        (p1, "ACTIVATE_NEW_VERIFIED_PUBLICATION", "Select the verified immutable controlled P1 for deployment.", "Explicit human approval to select controlled P1."),
        (p0, "ROLLBACK_TO_PRIOR_VERIFIED_PUBLICATION", "Select the prior verified immutable controlled P0 again.", "Explicit human approval to roll back selection to controlled P0."),
    ):
        p = proposal(target, kind, rationale)
        d = review(p, "APPROVE_FOR_ACTIVATION", note)
        old_pointer = deepcopy(registry.current_pointer)
        pointer = build_current_publication_pointer(registry_id=registry.value["registry_id"],
            generation=old_pointer["generation"]+1, target=target_descriptor(target),
            previous_pointer_hash=old_pointer["pointer_hash"], test_only=True)
        # Physical evidence, not a successful external-deployment simulation.
        evidence = verifier.verify(target) if verifier is not None else {
            "publication_tree_sha256": publication_tree_sha256(target.package_directory),
            "publication_attestation_sha256": hashlib.sha256(target.attestation_path.read_bytes()).hexdigest(),
            "expected_repository_semantic_hash": target.repository_semantic_hash,
            "live_repository_semantic_hash": target.repository_semantic_hash,
        }
        payload = build_execution_payload(proposal=p, decision=d, old_pointer=old_pointer,
            new_pointer=pointer, verification_evidence_hashes=evidence, test_only=True)
        registry.append_execution(event_type="ActivationApplied" if target is p1 else "RollbackApplied",
                                  execution_payload=payload, new_pointer=pointer)
    return reconstruct_controlled_history(registry.value, registry.current_pointer, authority=authority,
        expected_registry_hash=registry.value["registry_hash"], expected_head_event_hash=registry.value["head_event_hash"])
