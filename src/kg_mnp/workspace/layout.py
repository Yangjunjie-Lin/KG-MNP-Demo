"""Exact Project Workspace v1 directory contract."""

from __future__ import annotations

from pathlib import Path

WORKSPACE_LAYOUT_VERSION = "1.0.0"
DIRECTORIES = (
    "sources",
    "artifacts",
    "artifacts/evidence",
    "artifacts/ir",
    "artifacts/proposals",
    "artifacts/reviews",
    "artifacts/confirmed",
    "artifacts/builds",
    "artifacts/validation",
    "artifacts/packages",
    "registry",
    "reports",
    "tmp",
)
TOP_LEVEL_ENTRIES = {
    "project.yaml",
    "project.lock.json",
    "sources",
    "artifacts",
    "registry",
    "reports",
    "tmp",
}


def create_layout(root: Path) -> None:
    for relative in DIRECTORIES:
        (root / relative).mkdir(parents=True, exist_ok=False)


def layout_errors(root: Path) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    for relative in DIRECTORIES:
        path = root / relative
        if not path.is_dir() or path.is_symlink():
            errors.append(("WORKSPACE_LAYOUT_MISSING", relative))
    if root.is_dir():
        unknown = sorted(path.name for path in root.iterdir() if path.name not in TOP_LEVEL_ENTRIES)
        if unknown:
            errors.append(("UNEXPECTED_AUTHORITY_ENTRY", ", ".join(unknown)))
    return errors

