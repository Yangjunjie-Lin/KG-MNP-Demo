"""Immutable identity binding for all inputs used by diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from kg_mnp_demo.modeling.canonical_json import semantic_hash

from .errors import DiagnosticError, DiagnosticErrorCode


HASH_LENGTH = 64


def _hash(value: Any) -> str:
    return semantic_hash(value)


def _required_hash(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != HASH_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise DiagnosticError(
            DiagnosticErrorCode.AUTHORITY_MISMATCH,
            f"invalid {label}",
        )
    return value


@dataclass(frozen=True)
class AuthorityBindings:
    publication_id: str
    publication_semantic_hash: str
    phase01_attestation_hash: str
    phase02_attestation_hash: str
    query_registry_hash: str
    repository_semantic_hash: str
    diagnostic_policy_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.publication_id, str) or not self.publication_id:
            raise DiagnosticError(DiagnosticErrorCode.AUTHORITY_MISMATCH)
        for name in (
            "publication_semantic_hash",
            "phase01_attestation_hash",
            "phase02_attestation_hash",
            "query_registry_hash",
            "repository_semantic_hash",
            "diagnostic_policy_hash",
        ):
            _required_hash(getattr(self, name), name)
        if not self.publication_id.endswith(self.publication_semantic_hash):
            raise DiagnosticError(
                DiagnosticErrorCode.AUTHORITY_MISMATCH,
                "publication identifier/hash mismatch",
            )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AuthorityBindings":
        expected = set(cls.__dataclass_fields__)
        if set(value) != expected:
            raise DiagnosticError(
                DiagnosticErrorCode.AUTHORITY_MISMATCH,
                "authority binding field set mismatch",
            )
        return cls(**{key: str(value[key]) for key in expected})

    @classmethod
    def from_verified_documents(
        cls,
        *,
        publication_manifest: Mapping[str, Any],
        phase01_attestation: Mapping[str, Any],
        phase02_attestation: Mapping[str, Any],
        diagnostic_policy_hash: str,
    ) -> "AuthorityBindings":
        """Bind already verified Stage 08, Phase 01 and Phase 02 documents.

        Callers must run the existing authority validators before invoking this
        projection.  This method independently rejects stale or crossed lineage.
        """

        if phase01_attestation.get("status") != "APPLICATION_READONLY_VERIFIED":
            raise DiagnosticError(DiagnosticErrorCode.AUTHORITY_MISMATCH)
        if phase02_attestation.get("status") != "APPLICATION_WORKBENCH_VERIFIED":
            raise DiagnosticError(DiagnosticErrorCode.AUTHORITY_MISMATCH)
        publication_id = publication_manifest.get("publication_id")
        publication_hash = publication_manifest.get("publication_semantic_hash")
        repository_hash = (
            phase01_attestation.get("expected_graphdb_semantic_hash")
            or phase01_attestation.get("repository_semantic_hash")
        )
        phase01_pairs = (
            (phase01_attestation.get("publication_id"), publication_id),
            (phase01_attestation.get("publication_semantic_hash"), publication_hash),
        )
        phase02_pairs = (
            (phase02_attestation.get("publication_id"), publication_id),
            (phase02_attestation.get("publication_semantic_hash"), publication_hash),
            (phase02_attestation.get("repository_hash_expected"), repository_hash),
            (
                phase02_attestation.get("query_registry_hash"),
                phase01_attestation.get("query_registry_hash"),
            ),
        )
        if any(left != right for left, right in phase01_pairs + phase02_pairs):
            raise DiagnosticError(
                DiagnosticErrorCode.AUTHORITY_MISMATCH,
                "publication lineage mismatch",
            )
        embedded_phase01_hash = phase02_attestation.get("phase01_attestation_hash")
        actual_phase01_hash = (
            str(embedded_phase01_hash)
            if isinstance(embedded_phase01_hash, str)
            else _hash(dict(phase01_attestation))
        )
        _required_hash(actual_phase01_hash, "Phase 01 attestation hash")
        if embedded_phase01_hash is not None and embedded_phase01_hash != actual_phase01_hash:
            raise DiagnosticError(
                DiagnosticErrorCode.AUTHORITY_MISMATCH,
                "Phase 01 attestation identity mismatch",
            )
        return cls(
            publication_id=str(publication_id),
            publication_semantic_hash=str(publication_hash),
            phase01_attestation_hash=actual_phase01_hash,
            phase02_attestation_hash=_hash(dict(phase02_attestation)),
            query_registry_hash=str(phase01_attestation["query_registry_hash"]),
            repository_semantic_hash=str(repository_hash),
            diagnostic_policy_hash=diagnostic_policy_hash,
        )

    def verify_runtime_identity(self, current: Mapping[str, Any]) -> None:
        """Fail closed if a running read-only service is on other lineage."""

        expected = {
            "publication_id": self.publication_id,
            "publication_semantic_hash": self.publication_semantic_hash,
            "repository_semantic_hash": self.repository_semantic_hash,
            "query_registry_hash": self.query_registry_hash,
            "status": "APPLICATION_READONLY_VERIFIED",
        }
        if any(current.get(key) != value for key, value in expected.items()):
            raise DiagnosticError(DiagnosticErrorCode.DIAGNOSTICS_NOT_READY)
