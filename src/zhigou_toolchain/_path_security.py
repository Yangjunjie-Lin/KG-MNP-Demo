"""Fail-closed filesystem checks for reconstructed package boundaries."""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath


class UnsafePathError(ValueError):
    pass


def _is_link_like(path: Path) -> bool:
    """Return true for symlinks, junctions, and other Windows reparse points."""

    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _absolute_without_resolving(path: Path, *, label: str) -> Path:
    requested = Path(path)
    if ".." in requested.parts:
        raise UnsafePathError(f"{label} contains parent traversal")
    try:
        return Path(os.path.abspath(os.fspath(requested)))
    except (OSError, ValueError) as exc:
        raise UnsafePathError(f"{label} is not a valid local path") from exc


def _assert_components_are_local(path: Path, *, label: str) -> None:
    for component in (*reversed(path.parents), path):
        if _is_link_like(component):
            raise UnsafePathError(
                f"{label} contains a symlink, junction, or reparse point: {component}"
            )


def validated_directory(path: Path, *, label: str) -> Path:
    """Validate every lexical component before resolving an existing directory."""

    absolute = _absolute_without_resolving(Path(path), label=label)
    _assert_components_are_local(absolute, label=label)
    try:
        resolved = absolute.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise UnsafePathError(f"{label} is missing or cannot be resolved") from exc
    if not resolved.is_dir():
        raise UnsafePathError(f"{label} is not a directory")
    return resolved


def _relative_parts(relative: str, *, label: str) -> tuple[str, ...]:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise UnsafePathError(f"{label} is not a canonical relative POSIX path")
    posix_path = PurePosixPath(relative)
    native_path = Path(relative)
    if (
        posix_path.is_absolute()
        or native_path.is_absolute()
        or bool(native_path.drive)
        or any(part in {".", ".."} for part in posix_path.parts)
        or posix_path.as_posix() != relative
    ):
        raise UnsafePathError(f"{label} escapes or is not canonical")
    return posix_path.parts


def safe_artifact_path(directory: Path, relative: str, *, label: str) -> Path:
    """Return one regular artifact after lexical and resolved containment checks."""

    parts = _relative_parts(relative, label=label)
    candidate = directory.joinpath(*parts)
    _assert_components_are_local(candidate, label=label)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise UnsafePathError(f"{label} is missing or cannot be resolved") from exc
    if not resolved.is_relative_to(directory) or not resolved.is_file():
        raise UnsafePathError(f"{label} is not a contained regular file")
    return resolved


def closed_regular_files(directory: Path, *, label: str) -> dict[str, Path]:
    """Enumerate a package tree without following any link-like entry."""

    files: dict[str, Path] = {}
    pending = [directory]
    while pending:
        current = pending.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda entry: entry.name)
        except OSError as exc:
            raise UnsafePathError(f"{label} cannot be scanned safely") from exc
        for entry in entries:
            path = Path(entry.path)
            if _is_link_like(path):
                raise UnsafePathError(
                    f"{label} contains a symlink, junction, or reparse point: {path}"
                )
            try:
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    relative = path.relative_to(directory).as_posix()
                    _relative_parts(relative, label=f"{label} artifact")
                    files[relative] = path
                else:
                    raise UnsafePathError(
                        f"{label} contains a non-regular filesystem entry: {path}"
                    )
            except OSError as exc:
                raise UnsafePathError(
                    f"{label} entry cannot be classified safely: {path}"
                ) from exc
    return files
