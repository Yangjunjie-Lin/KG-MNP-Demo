"""Atomic, closed-set compilation artifact writing."""

from __future__ import annotations

import os
import shutil
import time
from collections.abc import Mapping
from pathlib import Path


class ArtifactWriteError(ValueError):
    pass


def _safe_directory(path: Path) -> Path:
    resolved = path.resolve()
    anchors = {Path(resolved.anchor).resolve(), Path.home().resolve()}
    if resolved in anchors or resolved.parent == resolved:
        raise ArtifactWriteError(f"unsafe compilation output directory: {resolved}")
    return resolved


def _commit_staging(staging: Path, target: Path) -> None:
    """Retry transient Windows sharing denials, without declaring success.

    Virus scanners/indexers can briefly hold a just-written staging directory.
    Only Win32 access/sharing denials on a still-existing source and absent
    target are retryable. Permanent denial remains a failed commit.
    """
    for attempt in range(6):
        try:
            os.replace(staging, target)
            return
        except PermissionError as exc:
            if (getattr(exc, "winerror", None) not in {5, 32, 33}
                    or attempt == 5 or target.exists() or not staging.is_dir()):
                raise
            time.sleep(min(0.05 * (2 ** attempt), 0.2))


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
        _commit_staging(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
