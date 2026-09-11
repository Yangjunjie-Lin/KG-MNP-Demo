"""Filesystem and structured-container security primitives."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .errors import SourceError


def require_regular_source(path: Path, *, max_bytes: int) -> Path:
    if "\x00" in str(path):
        raise SourceError("NULL_BYTE_REJECTED")
    try:
        if path.is_symlink():
            raise SourceError("SYMLINK_SOURCE_REJECTED")
        info = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise SourceError(f"cannot stat source: {path.name}: {exc}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise SourceError("source must be a regular file; FIFO/socket/device rejected")
    if info.st_size > max_bytes:
        raise SourceError(f"SOURCE_SIZE_LIMIT_EXCEEDED: {info.st_size} > {max_bytes}")
    return path.resolve(strict=True)


def safe_relative_display(value: Path) -> str:
    parts = value.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise SourceError("unsafe source display path")
    if value.is_absolute() or value.drive or value.root or str(value).startswith(("\\\\", "//")):
        raise SourceError("absolute display path rejected")
    text = value.as_posix()
    # Path.drive is host-dependent: POSIX must reject Windows drive syntax too.
    if "\\" in text or ":" in text or "\x00" in text:
        raise SourceError("unsafe source display path")
    return text


def fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
