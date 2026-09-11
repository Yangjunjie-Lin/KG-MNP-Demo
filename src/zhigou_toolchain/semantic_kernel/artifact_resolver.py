"""Closed, duplicate-detecting workspace artifact index."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.contracts.document_io import deterministic_json_bytes

from .errors import InputAttestationError

_ARTIFACT_ID = re.compile(r"^urn:kg-mnp:[a-z0-9-]+:[0-9a-f]{64}$")
_IDENTITY_FIELDS = {
    "KG_MNP_PROJECT_LOCK": "lock_id",
    "KG_MNP_ONTOLOGY_CONFIRMED_MODELING_PACKAGE": "package_id",
    "KG_MNP_ONTOLOGY_SCOPE": "scope_id",
    "KG_MNP_ONTOLOGY_SCOPE_APPROVAL": "approval_id",
    "KG_MNP_COMPETENCY_QUESTION_SET": "question_set_id",
    "KG_MNP_COMPETENCY_QUESTION_COVERAGE_REPORT": "coverage_report_id",
    "KG_MNP_KG_IR_DATASET": "dataset_id",
    "KG_MNP_KG_IR_ITEM": "item_id",
    "KG_MNP_EVIDENCE_RECORD": "evidence_id",
    "KG_MNP_SOURCE_ASSET": "source_id",
    "KG_MNP_TRANSFORMATION_RECORD": "transformation_id",
    "KG_MNP_ONTOLOGY_BASELINE_SNAPSHOT": "baseline_snapshot_id",
    "KG_MNP_TERMINOLOGY_CATALOG": "terminology_catalog_id",
    "KG_MNP_TERM_ALIGNMENT_SET": "term_alignment_set_id",
    "KG_MNP_FIELD_MAPPING_CANDIDATE_SET": "field_mapping_candidate_set_id",
    "KG_MNP_ONTOLOGY_MODELING_PROPOSAL": "proposal_id",
    "KG_MNP_FORMAL_PREVALIDATION_REPORT": "formal_prevalidation_report_id",
    "KG_MNP_ONTOLOGY_REVIEW_POLICY": "policy_id",
    "KG_MNP_ONTOLOGY_REVIEW_DECISION_LOG": "review_decision_log_id",
    "KG_MNP_PLUGIN_SNAPSHOT": "snapshot_id",
    "KG_MNP_MODEL_INVOCATION_RECORD": "invocation_id",
    "KG_MNP_INGESTION_PLAN": "plan_id",
    "KG_MNP_INGESTION_RUN": "run_id",
    "KG_MNP_COMPILER_INPUT_ATTESTATION": "attestation_id",
    "KG_MNP_SEMANTIC_COMPILATION_PLAN": "plan_id",
    "KG_MNP_SEMANTIC_COMPILER_SNAPSHOT": "snapshot_id",
    "KG_MNP_COMPETENCY_QUESTION_TEST_PLAN": "test_plan_id",
    "KG_MNP_SEMANTIC_COMPILATION_RUN": "run_id",
    "KG_MNP_ONTOLOGY_PACKAGE": "package_id",
}


@dataclass(frozen=True)
class ResolvedArtifact:
    artifact_id: str
    relative_path: str
    byte_sha256: str
    content_digest: str
    document: dict[str, Any]


class WorkspaceArtifactResolver:
    """Index safe JSON artifacts without selecting among ambiguous authorities."""

    def __init__(self, workspace: Path | str, *, max_file_bytes: int = 16_777_216) -> None:
        self.root = Path(workspace).resolve(strict=True)
        self.max_file_bytes = max_file_bytes
        self._index: dict[str, ResolvedArtifact] | None = None

    @staticmethod
    def _top_level_ids(document: dict[str, Any]) -> tuple[str, ...]:
        field = _IDENTITY_FIELDS.get(str(document.get("manifest_kind")))
        value = document.get(field) if field is not None else None
        return (value,) if isinstance(value, str) and _ARTIFACT_ID.fullmatch(value) else ()

    @classmethod
    def _authority_objects(cls, value: Any):
        if isinstance(value, dict):
            if isinstance(value.get("manifest_kind"), str) and cls._top_level_ids(value):
                yield value
            for item in value.values():
                yield from cls._authority_objects(item)
        elif isinstance(value, list):
            for item in value:
                yield from cls._authority_objects(item)

    def _scan(self) -> dict[str, ResolvedArtifact]:
        index: dict[str, ResolvedArtifact] = {}
        for path in sorted(self.root.rglob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve(strict=True)
            if self.root not in resolved.parents or path.stat().st_size > self.max_file_bytes:
                continue
            try:
                raw = path.read_bytes()
                document = json.loads(raw)
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if not isinstance(document, (dict, list)):
                continue
            relative = resolved.relative_to(self.root).as_posix()
            for authority in self._authority_objects(document):
                authority_bytes = deterministic_json_bytes(authority)
                byte_digest = hashlib.sha256(authority_bytes).hexdigest()
                content_digest = authority.get("content_digest")
                if not isinstance(content_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", content_digest):
                    content_digest = semantic_hash(authority)
                for artifact_id in self._top_level_ids(authority):
                    record = ResolvedArtifact(artifact_id, relative, byte_digest, content_digest, authority)
                    existing = index.get(artifact_id)
                    if existing is not None and existing.byte_sha256 != byte_digest:
                        raise InputAttestationError(
                            f"artifact ID occurs with different bytes: {artifact_id}",
                            code="DUPLICATE_ARTIFACT_ID",
                        )
                    if existing is None or relative < existing.relative_path:
                        index[artifact_id] = record
        return index

    @property
    def index(self) -> dict[str, ResolvedArtifact]:
        if self._index is None:
            self._index = self._scan()
        return dict(self._index)

    def resolve(self, artifact_id: str) -> ResolvedArtifact:
        record = self.index.get(artifact_id)
        if record is None:
            raise InputAttestationError(f"required workspace artifact is missing: {artifact_id}")
        return record

    def find_kind(self, manifest_kind: str) -> tuple[ResolvedArtifact, ...]:
        return tuple(
            item for item in self.index.values()
            if item.document.get("manifest_kind") == manifest_kind
        )
