"""Read-only live repository re-verification for activation and resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from kg_mnp_demo.application.readonly_client import ReadOnlyGraphDBClient
from kg_mnp_demo.graphdb.rdf_semantics import graphdb_semantic_hash_nquads

from .errors import ActivationError, ActivationErrorCode


class RepositoryHashReader(Protocol):
    """The complete GraphDB authority surface permitted to Phase 06."""

    def repository_semantic_hash(self, repository_id: str) -> str: ...


@dataclass(frozen=True, slots=True)
class ReadOnlyGraphDBRepositoryHashReader:
    client: ReadOnlyGraphDBClient

    def repository_semantic_hash(self, repository_id: str) -> str:
        try:
            info = self.client.repository_info(repository_id)
            reported = info.get("id") or info.get("repositoryID")
            if reported != repository_id:
                raise ValueError("repository identity mismatch")
            return graphdb_semantic_hash_nquads(
                self.client.export_explicit_nquads(repository_id)
            )
        except Exception as exc:
            raise ActivationError(
                ActivationErrorCode.TARGET_REPOSITORY_UNAVAILABLE,
                f"target repository is unavailable: {repository_id}",
            ) from exc


@dataclass(frozen=True, slots=True)
class StaticRepositoryHashReader:
    """Deterministic test-only reader; it has no graph mutation method."""

    hashes: Mapping[str, str]

    def repository_semantic_hash(self, repository_id: str) -> str:
        try:
            return self.hashes[repository_id]
        except KeyError as exc:
            raise ActivationError(
                ActivationErrorCode.TARGET_REPOSITORY_UNAVAILABLE
            ) from exc


def verify_live_repository(
    reader: RepositoryHashReader,
    *,
    repository_id: str,
    expected_semantic_hash: str,
) -> dict[str, str]:
    actual = reader.repository_semantic_hash(repository_id)
    if actual != expected_semantic_hash:
        raise ActivationError(
            ActivationErrorCode.TARGET_REPOSITORY_HASH_MISMATCH,
            "live target GraphDB semantic hash differs from the verified publication",
        )
    return {
        "repository_id": repository_id,
        "expected_repository_semantic_hash": expected_semantic_hash,
        "actual_repository_semantic_hash": actual,
        "status": "TARGET_REPOSITORY_REVERIFIED",
    }
