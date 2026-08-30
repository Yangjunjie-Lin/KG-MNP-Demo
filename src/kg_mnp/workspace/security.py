"""Project Workspace filesystem confinement checks."""

from __future__ import annotations

from pathlib import Path

from kg_mnp.contracts.errors import PathSecurityError


def validate_workspace_tree(root: Path) -> None:
    resolved_root = root.resolve(strict=True)
    if root.is_symlink():
        raise PathSecurityError("Workspace root must not be a symlink")
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            try:
                path.resolve(strict=True).relative_to(resolved_root)
            except (OSError, ValueError) as exc:
                raise PathSecurityError(f"Workspace symlink escapes root: {relative}") from exc
            raise PathSecurityError(f"Workspace symlinks are forbidden: {relative}")
        if not path.is_dir() and not path.is_file():
            raise PathSecurityError(f"non-regular Workspace entry: {relative}")


def confirmed_authority_files(root: Path) -> tuple[str, ...]:
    confirmed = root / "artifacts" / "confirmed"
    if not confirmed.is_dir():
        return ()
    return tuple(
        path.relative_to(root).as_posix()
        for path in sorted(confirmed.rglob("*"))
        if path.is_file()
    )

