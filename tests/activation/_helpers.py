from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kg_mnp_demo.activation.errors import ActivationError, ActivationErrorCode
from kg_mnp_demo.modeling.canonical_json import semantic_hash


def _hash(character: str) -> str:
    return character * 64


@dataclass(frozen=True)
class FakeTarget:
    publication_id: str
    publication_semantic_hash: str
    repository_id: str
    repository_semantic_hash: str
    publication_attestation_sha256: str
    lineage_source_type: str
    lineage_source_attestation_sha256: str

    @property
    def descriptor(self) -> dict[str, str]:
        return {
            "publication_id": self.publication_id,
            "publication_semantic_hash": self.publication_semantic_hash,
            "repository_id": self.repository_id,
            "repository_semantic_hash": self.repository_semantic_hash,
            "publication_attestation_sha256": self.publication_attestation_sha256,
            "lineage_source_type": self.lineage_source_type,
            "lineage_source_attestation_sha256": self.lineage_source_attestation_sha256,
        }


class FakeAuthority:
    test_only = True
    production_authority = False

    def __init__(self) -> None:
        self.base_publication = FakeTarget(
            "urn:kg-mnp:test-fixture:phase06:publication:p0",
            _hash("0"),
            "kg-mnp-phase06-p0",
            _hash("a"),
            _hash("b"),
            "CONTROLLED_PHASE06_BOOTSTRAP",
            _hash("c"),
        )
        self.activation_candidates = (
            FakeTarget(
                "urn:kg-mnp:test-fixture:phase06:publication:p1",
                _hash("1"),
                "kg-mnp-phase06-p1",
                _hash("d"),
                _hash("e"),
                "CONTROLLED_PHASE05_VERIFIED_PUBLICATION",
                _hash("f"),
            ),
        )

    @property
    def binding(self) -> dict[str, Any]:
        return {
            "authority_type": "CONTROLLED_TEST_HARNESS",
            "base_publication": self.base_publication.descriptor,
            "activation_candidates": [
                item.descriptor for item in self.activation_candidates
            ],
            "test_only": True,
            "production_authority": False,
        }

    @property
    def binding_hash(self) -> str:
        return semantic_hash(self.binding)

    def resolve_target(self, publication_id: str) -> FakeTarget:
        for target in (self.base_publication, *self.activation_candidates):
            if target.publication_id == publication_id:
                return target
        raise ActivationError(ActivationErrorCode.UNVERIFIED_ACTIVATION_TARGET)

    def target_binding_hash(self, publication_id: str) -> str:
        return semantic_hash(
            {
                "authority_binding_hash": self.binding_hash,
                "target": self.resolve_target(publication_id).descriptor,
            }
        )


@dataclass
class FakeVerifier:
    unavailable_repository_id: str | None = None
    mismatch_repository_id: str | None = None

    def verify(self, target: object) -> dict[str, str]:
        descriptor = target.descriptor  # type: ignore[attr-defined]
        if descriptor["repository_id"] == self.unavailable_repository_id:
            raise ActivationError(ActivationErrorCode.TARGET_REPOSITORY_UNAVAILABLE)
        live = descriptor["repository_semantic_hash"]
        if descriptor["repository_id"] == self.mismatch_repository_id:
            live = _hash("9")
        return {
            "publication_tree_sha256": semantic_hash(
                {"publication": descriptor["publication_id"]}
            ),
            "publication_attestation_sha256": descriptor[
                "publication_attestation_sha256"
            ],
            "expected_repository_semantic_hash": descriptor["repository_semantic_hash"],
            "live_repository_semantic_hash": live,
        }


def create_approved_proposal(controller, authority: FakeAuthority) -> tuple[dict, dict]:
    state = controller.status()
    proposal = controller.create_proposal(
        target_publication_id=authority.activation_candidates[0].publication_id,
        activation_kind="ACTIVATE_NEW_VERIFIED_PUBLICATION",
        rationale="Explicit controlled deployment selection.",
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
    decision = controller.record_review(
        proposal["activation_proposal_id"],
        decision="APPROVE_FOR_ACTIVATION",
        reviewed_by_label="reviewer-label",
        review_note="Explicit human deployment approval.",
        explicit_human_action=True,
        expected_registry_revision=state["registry_revision"],
        expected_head_event_hash=state["head_event_hash"],
    )
    return proposal, decision
