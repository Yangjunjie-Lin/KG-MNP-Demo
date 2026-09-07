"""Content-addressed local SourceAsset and SourceBatch store."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

from kg_mnp.contracts.canonical import bytes_sha256, semantic_hash, stable_urn
from kg_mnp.contracts.document_io import atomic_write_bytes, atomic_write_json
from kg_mnp.contracts.registry import validate_contract
from kg_mnp.workspace.service import open_workspace

from .contracts import finalize_document, verify_finalized_document
from .errors import SourceError, SourceTamperedError
from .limits import DEFAULT_LIMITS, ResourceLimits
from .media_detection import detect_media_type
from .models import SourceRegistrationResult
from .security import require_regular_source, safe_relative_display
from .transaction import WorkspaceOperationLock

SOURCE_IDENTITY_PROFILE = "KG-MNP Source Identity v1"


class SourceStore:
    def __init__(self, workspace: Path | str, *, limits: ResourceLimits = DEFAULT_LIMITS) -> None:
        opened = open_workspace(workspace)
        self.workspace = opened.root
        self.project_lock_id = opened.lock.lock_id
        self.limits = limits
        self.sources_root = self.workspace / "sources"
        self.blob_root = self.sources_root / "blobs" / "sha256"
        self.records_root = self.sources_root / "records"
        self.batches_root = self.sources_root / "batches"
        for directory in (self.blob_root, self.records_root, self.batches_root):
            directory.mkdir(parents=True, exist_ok=True)
            if directory.is_symlink():
                raise SourceError("Source Store directory must not be a symlink")

    @staticmethod
    def _hash_from_id(identifier: str) -> str:
        value = identifier.rsplit(":", 1)[-1]
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            raise SourceError("invalid deterministic identifier")
        return value

    def _record_path(self, source_id: str) -> Path:
        return self.records_root / f"{self._hash_from_id(source_id)}.json"

    def _batch_path(self, batch_id: str) -> Path:
        return self.batches_root / f"{self._hash_from_id(batch_id)}.json"

    def _blob_path(self, digest: str) -> Path:
        return self.blob_root / digest[:2] / digest

    def add_file(
        self,
        path: Path | str,
        *,
        declared_media_type: str | None = None,
        source_origin: str = "local-file",
        display_path: Path | None = None,
        display_name: str | None = None,
    ) -> SourceRegistrationResult:
        source = require_regular_source(Path(path), max_bytes=self.limits.max_source_bytes)
        content = source.read_bytes()
        if len(content) > self.limits.max_source_bytes:
            raise SourceError(
                f"SOURCE_SIZE_LIMIT_EXCEEDED: {len(content)} > {self.limits.max_source_bytes}"
            )
        name = display_name if display_name is not None else source.name
        if not name or any(char in name for char in "\\/:\x00\r\n") or len(name) > 200:
            raise SourceError("invalid display filename")
        detection = detect_media_type(
            content,
            name,
            declared_media_type=declared_media_type,
            limits=self.limits,
        )
        content_sha = bytes_sha256(content)
        identity = {
            "content_sha256": content_sha,
            "detected_media_type": detection.detected_media_type,
            "identity_profile": SOURCE_IDENTITY_PROFILE,
        }
        source_id = stable_urn("source", identity)
        safe_display = safe_relative_display(display_path or Path(name))
        blob_relative = f"sources/blobs/sha256/{content_sha[:2]}/{content_sha}"
        record = {
            "manifest_kind": "KG_MNP_SOURCE_ASSET",
            "schema_version": "1.0.0",
            "source_id": source_id,
            "content_sha256": content_sha,
            "content_digest": "",
            "size_bytes": len(content),
            "detected_media_type": detection.detected_media_type,
            "declared_media_type": declared_media_type,
            "original_name": name,
            "safe_display_path": safe_display,
            "source_origin": source_origin,
            "blob_path": blob_relative,
            "registration_method": "copied",
            "metadata": {
                "identity_profile": SOURCE_IDENTITY_PROFILE,
                "detection_basis": list(detection.confidence_basis),
                "media_conflicts": list(detection.conflicts),
            },
            "extensions": {},
        }
        record["content_digest"] = semantic_hash({k: v for k, v in record.items() if k != "content_digest"})
        validate_contract("source-asset", record)
        record_path = self._record_path(source_id)
        blob_path = self._blob_path(content_sha)
        with WorkspaceOperationLock(self.workspace, "source"):
            duplicate = record_path.exists()
            if blob_path.exists():
                if not blob_path.is_file() or blob_path.is_symlink() or bytes_sha256(blob_path.read_bytes()) != content_sha:
                    raise SourceTamperedError("existing Source Blob hash mismatch")
            else:
                blob_path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_bytes(blob_path, content)
            if record_path.exists():
                existing = self.load_source(source_id)
                if existing["content_sha256"] != content_sha or existing["detected_media_type"] != detection.detected_media_type:
                    raise SourceTamperedError("Source ID collision with different identity")
                record = existing
            else:
                atomic_write_json(record_path, record)
        return SourceRegistrationResult(source=record, duplicate=duplicate)

    def add_directory(
        self,
        directory: Path | str,
        *,
        recursive: bool = False,
        declared_media_type: str | None = None,
        max_depth: int = 16,
        include_hidden: bool = False,
    ) -> tuple[SourceRegistrationResult, ...]:
        root = Path(directory)
        if root.is_symlink() or not root.is_dir():
            raise SourceError("source directory must be a non-symlink directory")
        root = root.resolve(strict=True)
        candidates: list[Path] = []
        iterator = root.rglob("*") if recursive else root.iterdir()
        for candidate in iterator:
            relative = candidate.relative_to(root)
            if any(part.startswith(".") for part in relative.parts) and not include_hidden:
                continue
            if len(relative.parts) > max_depth:
                raise SourceError("DIRECTORY_DEPTH_LIMIT_EXCEEDED")
            if candidate.is_symlink():
                raise SourceError(f"SYMLINK_SOURCE_REJECTED: {relative.as_posix()}")
            if candidate.is_dir():
                continue
            require_regular_source(candidate, max_bytes=self.limits.max_source_bytes)
            candidates.append(candidate)
        candidates.sort(key=lambda item: item.relative_to(root).as_posix())
        if len(candidates) > self.limits.max_sources_per_batch:
            raise SourceError("SOURCE_COUNT_LIMIT_EXCEEDED")
        total = sum(item.stat().st_size for item in candidates)
        if total > self.limits.max_source_bytes * self.limits.max_sources_per_batch:
            raise SourceError("DIRECTORY_TOTAL_BYTE_LIMIT_EXCEEDED")
        return tuple(
            self.add_file(
                item,
                declared_media_type=declared_media_type,
                source_origin="local-directory",
                display_path=item.relative_to(root),
            )
            for item in candidates
        )

    def list_sources(self) -> tuple[dict, ...]:
        return tuple(
            self._read_json(path)
            for path in sorted(self.records_root.glob("*.json"), key=lambda item: item.name)
        )

    @staticmethod
    def _read_json(path: Path) -> dict:
        try:
            value = json.loads(path.read_bytes())
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SourceError(f"invalid stored source document {path.name}: {exc}") from exc
        if not isinstance(value, dict):
            raise SourceError(f"stored source document is not an object: {path.name}")
        return value

    def load_source(self, source_id: str) -> dict:
        path = self._record_path(source_id)
        if not path.is_file() or path.is_symlink():
            raise SourceError(f"unknown SourceAsset: {source_id}")
        value = self._read_json(path)
        validate_contract("source-asset", value)
        return value

    def blob_for(self, source: dict) -> Path:
        expected = self._blob_path(source["content_sha256"])
        if source["blob_path"] != expected.relative_to(self.workspace).as_posix():
            raise SourceTamperedError("SourceAsset blob_path does not match content hash")
        return expected

    def verify_source(self, source_id: str) -> dict:
        source = self.load_source(source_id)
        identity = {
            "content_sha256": source["content_sha256"],
            "detected_media_type": source["detected_media_type"],
            "identity_profile": SOURCE_IDENTITY_PROFILE,
        }
        if source["source_id"] != stable_urn("source", identity):
            raise SourceTamperedError("SourceAsset deterministic ID mismatch")
        digest = semantic_hash({k: v for k, v in source.items() if k != "content_digest"})
        if source["content_digest"] != digest:
            raise SourceTamperedError("SourceAsset content digest mismatch")
        blob = self.blob_for(source)
        if not blob.is_file() or blob.is_symlink():
            raise SourceTamperedError("Source Blob missing or unsafe")
        if bytes_sha256(blob.read_bytes()) != source["content_sha256"]:
            raise SourceTamperedError("Source Blob hash mismatch")
        return source

    def create_batch(self, source_ids: Iterable[str], *, labels: Iterable[str] = ()) -> dict:
        unique = sorted(set(source_ids))
        if not unique:
            raise SourceError("SourceBatch requires at least one source")
        if len(unique) > self.limits.max_sources_per_batch:
            raise SourceError("SOURCE_COUNT_LIMIT_EXCEEDED")
        for source_id in unique:
            self.verify_source(source_id)
        batch = finalize_document(
            {
                "manifest_kind": "KG_MNP_SOURCE_BATCH",
                "schema_version": "1.0.0",
                "project_lock_id": self.project_lock_id,
                "sources": unique,
                "labels": sorted(set(labels)),
            },
            contract="source-batch",
            id_field="batch_id",
            urn_kind="source-batch",
        )
        path = self._batch_path(batch["batch_id"])
        with WorkspaceOperationLock(self.workspace, "source"):
            if path.exists():
                existing = self._read_json(path)
                if existing != batch:
                    raise SourceTamperedError("existing SourceBatch differs")
            else:
                atomic_write_json(path, batch)
        return batch

    def load_batch(self, batch_id: str) -> dict:
        path = self._batch_path(batch_id)
        if not path.is_file() or path.is_symlink():
            raise SourceError(f"unknown SourceBatch: {batch_id}")
        batch = self._read_json(path)
        verify_finalized_document(batch, contract="source-batch", id_field="batch_id", urn_kind="source-batch")
        if batch["project_lock_id"] != self.project_lock_id:
            raise SourceTamperedError("SourceBatch ProjectLock binding mismatch")
        for source_id in batch["sources"]:
            self.verify_source(source_id)
        return batch

    def list_batches(self) -> tuple[dict, ...]:
        return tuple(self._read_json(path) for path in sorted(self.batches_root.glob("*.json")))
