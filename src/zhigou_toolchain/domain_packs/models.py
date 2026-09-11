"""Public Domain Pack value models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DomainPackManifest:
    document: dict[str, Any]
    path: Path

    @property
    def pack_id(self) -> str:
        return self.document["pack_id"]

    @property
    def pack_version(self) -> str:
        return self.document["pack_version"]

    @property
    def capabilities(self) -> tuple[str, ...]:
        return tuple(self.document["capabilities"])


@dataclass(frozen=True)
class DomainPackLock:
    document: dict[str, Any]
    path: Path

    @property
    def lock_id(self) -> str:
        return self.document["lock_id"]

    @property
    def content_digest(self) -> str:
        return self.document["content_digest"]


@dataclass(frozen=True)
class ResolvedDomainPack:
    root: Path
    manifest: DomainPackManifest
    lock: DomainPackLock
    dependency_depth: int = 0


@dataclass(frozen=True)
class DomainPackValidationResult:
    report: dict[str, Any]
    manifest: DomainPackManifest | None = None

    @property
    def valid(self) -> bool:
        return self.report["status"] == "VALID"

