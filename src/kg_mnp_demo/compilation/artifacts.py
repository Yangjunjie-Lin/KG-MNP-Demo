"""Atomic, closed-set compilation artifact writing."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Mapping


class ArtifactWriteError(ValueError):
    pass


def _safe_directory(path: Path) -> Path:
    resolved = path.resolve()
    anchors = {Path(resolved.anchor).resolve(), Path.home().resolve()}
    if resolved in anchors or resolved.parent == resolved:
        raise ArtifactWriteError(f"unsafe compilation output directory: {resolved}")
    return resolved


def write_artifact_set(output_dir: Path, files: Mapping[str, bytes], *, force: bool = False) -> None:
    target = _safe_directory(output_dir)
    staging = target.parent / f".{target.name}.staging"
    _safe_directory(staging)
    if target.exists() and not force:
        raise FileExistsError(f"output already exists; pass --force to replace it: {target}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        for relative, data in sorted(files.items()):
            path = staging / Path(relative)
            resolved = path.resolve()
            if staging not in resolved.parents:
                raise ArtifactWriteError(f"artifact escapes compilation directory: {relative}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if target.exists():
            shutil.rmtree(target)
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
