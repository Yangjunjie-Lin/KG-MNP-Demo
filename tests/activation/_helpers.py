from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kg_mnp.activation.errors import ActivationError, ActivationErrorCode
from kg_mnp.modeling.canonical_json import semantic_hash


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
