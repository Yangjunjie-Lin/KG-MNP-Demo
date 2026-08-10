"""Bind Phase 02 to one independently verified Phase 01 artifact."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kg_mnp_demo.application.artifact_verifier import (
    verify_application_phase01_artifact,
)
from kg_mnp_demo.application.contracts import validate_application_contract

from .contracts import strict_json_file
from .errors import WorkbenchError, WorkbenchErrorCode


PHASE01_BASELINE_SHA = "79b7d34125b0c5cb2d5fe8546e1f4e6a95ca8106"
STAGE08_BASELINE_SHA = "4dc09d9cfb15da3746f108755593ceb9fe805cd7"


@dataclass(frozen=True)
class WorkbenchBinding:
    """The complete authority identity Phase 02 is permitted to display."""

    phase01_artifact_directory: Path
    phase01_attestation_hash: str
    phase01_attestation_status: str
    publication_id: str
    publication_semantic_hash: str
    repository_id: str
    repository_semantic_hash: str
    query_registry_hash: str

    @classmethod
    def load(cls, artifact_directory: Path) -> "WorkbenchBinding":
        root = Path(artifact_directory)
        try:
            verified = verify_application_phase01_artifact(root)
            attestation_path = root / "application-attestation.json"
            raw = attestation_path.read_bytes()
            attestation = strict_json_file(attestation_path)
            validate_application_contract(
                "application-phase01-attestation",
                attestation,
            )
        except Exception as exc:
            raise WorkbenchError(WorkbenchErrorCode.WORKBENCH_NOT_READY) from exc
        if verified.get("status") != "APPLICATION_READONLY_VERIFIED":
            raise WorkbenchError(WorkbenchErrorCode.WORKBENCH_NOT_READY)
        return cls(
            phase01_artifact_directory=root.resolve(),
            phase01_attestation_hash=hashlib.sha256(raw).hexdigest(),
            phase01_attestation_status=attestation["status"],
            publication_id=attestation["publication_id"],
            publication_semantic_hash=attestation["publication_semantic_hash"],
            repository_id=attestation["repository_id"],
            repository_semantic_hash=attestation[
                "expected_graphdb_semantic_hash"
            ],
            query_registry_hash=attestation["query_registry_hash"],
        )

    def verify_health(self, health: Any) -> None:
        if not isinstance(health, dict):
            raise WorkbenchError(WorkbenchErrorCode.WORKBENCH_NOT_READY)
        authority = health.get("publication_authority_reconstruction")
        expected = {
            "status": "APPLICATION_READY",
            "read_only": True,
            "publication_id": self.publication_id,
            "publication_semantic_hash": self.publication_semantic_hash,
            "repository_id": self.repository_id,
            "expected_graphdb_semantic_hash": self.repository_semantic_hash,
            "live_graphdb_semantic_hash": self.repository_semantic_hash,
            "repository_semantic_identity_verified": True,
        }
        if any(health.get(key) != value for key, value in expected.items()):
            raise WorkbenchError(WorkbenchErrorCode.WORKBENCH_NOT_READY)
        if (
            not isinstance(authority, dict)
            or authority.get("status") != "PASS"
            or authority.get("publication_id") != self.publication_id
            or authority.get("deterministic_reconstruction_match") is not True
        ):
            raise WorkbenchError(WorkbenchErrorCode.WORKBENCH_NOT_READY)

    def verify_query_result(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            raise WorkbenchError(WorkbenchErrorCode.PHASE01_RESPONSE_INVALID)
        if (
            payload.get("publication_id") != self.publication_id
            or payload.get("publication_semantic_hash")
            != self.publication_semantic_hash
            or payload.get("repository_id") != self.repository_id
            or payload.get("traceability", {})
            .get("publication", {})
            .get("publication_id")
            != self.publication_id
        ):
            raise WorkbenchError(WorkbenchErrorCode.WORKBENCH_NOT_READY)

    def public_status(self) -> dict[str, Any]:
        return {
            "foundation_verified": True,
            "phase01_verified": True,
            "phase01_attestation_status": self.phase01_attestation_status,
            "phase01_attestation_hash": self.phase01_attestation_hash,
            "publication_id": self.publication_id,
            "publication_semantic_hash": self.publication_semantic_hash,
            "repository_id": self.repository_id,
            "repository_semantic_hash": self.repository_semantic_hash,
            "query_registry_hash": self.query_registry_hash,
        }
