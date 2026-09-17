"""Bounded, no-overwrite exchange snapshots. No receiver state is modified."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path, PurePosixPath

from zhigou_toolchain._path_security import _is_link_like

MAX_BYTES = 64_000_000


@contextmanager
def reservation(path):
    path = checked_path(path)
    with path.open("xb"):
        pass
    try:
        yield
    finally:
        # Close the handle before unlinking (also required on Windows).
        path.unlink()


def require(condition, code):
    if not condition:
        raise ValueError(code)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_name(name):
    require(isinstance(name, str) and bool(name) and not any(ord(c) < 32 or c in '\\:<>"|?*' for c in name), "UNSAFE_EXCHANGE_PATH")
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name and all(
        p not in {".", "..", ""} and not p.endswith((".", " "))
        and not re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", p)
        for p in path.parts), "UNSAFE_EXCHANGE_PATH")
    return name


def checked_path(path):
    path = Path(path).absolute()
    require(not any(_is_link_like(p) for p in (path, *path.parents)), "EXCHANGE_LINK_FORBIDDEN")
    return path


def read_bounded(path, *, limit=MAX_BYTES):
    path = checked_path(path)
    require(path.is_file(), "EXCHANGE_FILE_LIMIT")
    observed_size = path.stat().st_size
    require(observed_size <= limit, "EXCHANGE_FILE_LIMIT")
    with path.open("rb") as stream:
        raw = stream.read(observed_size + 1)
    require(len(raw) == observed_size and len(raw) <= limit, "EXCHANGE_FILE_CHANGED_OR_LIMIT")
    return raw


def atomic_file(path, raw):
    """Exclusive same-directory reservation, fsync then rename; never replace."""
    path = checked_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(len(raw) <= MAX_BYTES, "EXCHANGE_FILE_LIMIT")
    lock = path.with_name(path.name + ".lock")
    with reservation(lock):
        temporary = None
        try:
            require(not path.exists(), "EXCHANGE_OUTPUT_EXISTS")
            fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
            temporary = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            require(not path.exists(), "EXCHANGE_OUTPUT_EXISTS")
            temporary.rename(path)
        finally:
            # Only our exclusive temporary/lock, never a user's output.
            if temporary is not None and temporary.exists():
                temporary.unlink()


def file_rows(files, *, upstream=False):
    return [{("name" if upstream else "path"): safe_name(name), "sha256": digest(raw),
             ("size" if upstream else "size_bytes"): len(raw)} for name, raw in sorted(files.items())]


def verify_rows(files, rows, *, upstream=False):
    seen = set()
    for row in rows:
        name = safe_name(row["name" if upstream else "path"])
        require(name.casefold() not in seen, "DUPLICATE_MANIFEST_PATH")
        seen.add(name.casefold())
        require(name in files, "MANIFEST_FILE_MISSING")
        raw = files[name]
        size = row["size" if upstream else "size_bytes"]
        require(type(size) is int and size == len(raw) and row["sha256"] == digest(raw), "MANIFEST_BYTES_MISMATCH")
    return seen


def read_directory(root):
    root = checked_path(root)
    require(root.is_dir(), "EXCHANGE_DIRECTORY_REQUIRED")
    files = {}
    total = 0
    for path in sorted(root.rglob("*")):
        checked_path(path)
        if path.is_file():
            name = safe_name(path.relative_to(root).as_posix())
            raw = read_bounded(path)
            total += len(raw)
            require(total <= MAX_BYTES and len(files) < 4096, "EXCHANGE_TOTAL_LIMIT")
            files[name] = raw
    require(len({n.casefold() for n in files}) == len(files), "EXCHANGE_CASE_COLLISION")
    return files


def read_archive(raw):
    """Bounded in-memory extraction, never execute a member or follow a link."""
    require(0 < len(raw) <= MAX_BYTES, "ZIP_SIZE_LIMIT")
    files, seen, total = {}, set(), 0
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        require(len(archive.infolist()) <= 4096, "ZIP_ENTRY_COUNT_LIMIT")
        for entry in archive.infolist():
            require(entry.orig_filename == entry.filename, "ZIP_FILENAME_NORMALIZATION_FORBIDDEN")
            name = safe_name(entry.filename.rstrip("/") if entry.is_dir() else entry.filename)
            require(name.casefold() not in seen, "DUPLICATE_ZIP_PATH")
            seen.add(name.casefold())
            mode = (entry.external_attr >> 16) & 0o170000
            require(mode in {0, 0o100000, 0o040000} and not entry.flag_bits & 1, "ZIP_LINK_OR_ENCRYPTION_FORBIDDEN")
            if entry.is_dir():
                continue
            total += entry.file_size
            require(total <= MAX_BYTES and entry.file_size <= max(1, entry.compress_size) * 1000, "ZIP_EXPANSION_LIMIT")
            files[name] = archive.read(entry)
    require(not any(n + "/" == other[:len(n) + 1] for n in files for other in files if n != other), "ZIP_FILE_DIRECTORY_COLLISION")
    return files


def write_directory(output, files, *, manifest):
    output = checked_path(output)
    require(manifest in files and sum(map(len, files.values())) <= MAX_BYTES, "EXCHANGE_TOTAL_LIMIT")
    require(len({safe_name(n).casefold() for n in files}) == len(files), "EXCHANGE_CASE_COLLISION")
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.with_name(output.name + ".lock")
    with reservation(lock):
        require(not output.exists(), "EXCHANGE_OUTPUT_EXISTS")
        staging = Path(tempfile.mkdtemp(prefix=output.name + "-", suffix=".tmp", dir=output.parent))
        # A failure intentionally leaves incomplete .tmp material for diagnosis.
        for name in [*sorted(set(files) - {manifest}), manifest]:
            atomic_file(staging / name, files[name])
        require(not output.exists(), "EXCHANGE_OUTPUT_EXISTS")
        staging.rename(output)
    return output
