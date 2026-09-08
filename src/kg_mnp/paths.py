"""Central path resolution for repository development, Domain Packs, and runtime.

Prompt 1 does not define the final Project Workspace contract.  These helpers
remove scattered source-tree parent arithmetic while keeping the three current
path authorities explicit and independently testable.
"""

from __future__ import annotations

import os
from pathlib import Path

_REPOSITORY_MARKERS = ("pyproject.toml", "domain_packs")


def _discover_repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if all((candidate / marker).exists() for marker in _REPOSITORY_MARKERS):
            return candidate
    raise RuntimeError("cannot locate KG-MNP repository development root")


def repository_root() -> Path:
    """Return the checked-out repository root for development-time assets."""

    return _discover_repository_root(Path(__file__).resolve().parent)


def domain_packs_root(*, repository: Path | None = None) -> Path:
    """Return the provisional repository Domain Pack root."""

    base = repository.resolve() if repository is not None else repository_root()
    return base / "domain_packs"


def domain_pack_path(
    pack_id: str = "mnp",
    *,
    repository: Path | None = None,
) -> Path:
    """Resolve a simple local pack identifier without accepting path traversal."""

    if (not isinstance(pack_id, str) or not pack_id or pack_id in {".", ".."}
            or any(char in pack_id for char in "/\\:\0") or Path(pack_id).name != pack_id):
        raise ValueError(f"unsafe Domain Pack identifier: {pack_id!r}")
    return domain_packs_root(repository=repository) / pack_id


def runtime_workspace_root() -> Path:
    """Return the local runtime workspace without creating it.

    ``KG_MNP_WORKSPACE`` is an explicit runtime override.  The default remains
    repository-local and ignored until the later Workspace Contract is defined.
    """

    configured = os.environ.get("KG_MNP_WORKSPACE")
    if configured:
        return Path(configured).expanduser().resolve()
    return repository_root() / "workspace"
