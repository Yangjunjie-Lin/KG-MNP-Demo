"""Registry-local content-addressed storage facade."""
from __future__ import annotations

from pathlib import Path

from ..security import child, storage_key
from ..store import list_records, load, save


def object_path(workspace: Path | str, identifier: str, suffix: str = ".kgop") -> Path:
    root = Path(workspace)
    key = storage_key(identifier)
    return child(root, f"objects/sha256/{key[:2]}/{key}{suffix}")


__all__ = ["child", "list_records", "load", "object_path", "save", "storage_key"]
