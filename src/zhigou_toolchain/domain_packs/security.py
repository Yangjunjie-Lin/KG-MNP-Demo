"""Filesystem and data-only security policy for Domain Packs."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from zhigou_toolchain.contracts.errors import PathSecurityError
from zhigou_toolchain.contracts.identifiers import (
    resolve_within,
    validate_safe_relative_path,
)

EXECUTABLE_SUFFIXES = {
    ".bat", ".bin", ".cmd", ".com", ".dll", ".dylib", ".exe", ".jar",
    ".js", ".msi", ".ps1", ".py", ".sh", ".so", ".vbs",
}
SEMANTIC_SUFFIXES = {
    ".json", ".jsonld", ".n3", ".nt", ".nq", ".owl", ".rdf", ".rq",
    ".schema.json", ".shacl", ".trig", ".ttl", ".xml", ".yaml", ".yml",
}
METADATA_PATHS = {"README.md", "pack.yaml", "pack.lock.json"}


def asset_path(pack_root: Path, relative: str) -> Path:
    validate_safe_relative_path(relative)
    return resolve_within(pack_root, relative)


def is_executable_content(path: Path) -> bool:
    lowered = path.name.casefold()
    if any(lowered.endswith(suffix) for suffix in EXECUTABLE_SUFFIXES):
        return True
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        raise PathSecurityError(f"cannot inspect asset permissions: {path.name}") from exc
    return os.name != "nt" and bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def semantic_files(pack_root: Path) -> tuple[str, ...]:
    result: list[str] = []
    root = pack_root.resolve(strict=True)
    for path in sorted(pack_root.rglob("*")):
        relative = path.relative_to(pack_root).as_posix()
        if path.is_symlink():
            resolved = path.resolve(strict=True)
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise PathSecurityError(f"symlink escapes Domain Pack: {relative}") from exc
        if not path.is_file():
            continue
        lowered = path.name.casefold()
        suffix = ".schema.json" if lowered.endswith(".schema.json") else path.suffix.casefold()
        if suffix in SEMANTIC_SUFFIXES and relative not in METADATA_PATHS:
            result.append(relative)
        if is_executable_content(path):
            raise PathSecurityError(f"executable content is forbidden in Domain Pack: {relative}")
    return tuple(result)

