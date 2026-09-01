"""Small immutable values shared by compiler stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdflib import Graph


@dataclass(frozen=True)
class CompilationResult:
    graph: Graph
    report: dict[str, Any]
    item_triples: dict[str, tuple[tuple[Any, Any, Any], ...]]


@dataclass(frozen=True)
class PackageBuildResult:
    build_id: str
    package_id: str
    package_directory: Path
    archive_path: Path | None
    artifacts: dict[str, bytes]
