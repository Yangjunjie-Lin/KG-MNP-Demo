"""Project Workspace public value models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProjectManifest:
    document: dict[str, Any]
    path: Path

    @property
    def project_id(self) -> str:
        return self.document["project_id"]

    @property
    def project_version(self) -> str:
        return self.document["project_version"]


@dataclass(frozen=True)
class ProjectLock:
    document: dict[str, Any]
    path: Path

    @property
    def lock_id(self) -> str:
        return self.document["lock_id"]


@dataclass(frozen=True)
class ProjectWorkspace:
    root: Path
    manifest: ProjectManifest
    lock: ProjectLock


@dataclass(frozen=True)
class WorkspaceValidationResult:
    report: dict[str, Any]
    status: str

    @property
    def valid(self) -> bool:
        return self.status == "VALID"

