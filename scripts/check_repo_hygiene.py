#!/usr/bin/env python3
"""Fail on tracked runtime/build files, virtualenvs, or local absolute paths."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ABS_PATH_PATTERNS = [
    re.compile(r"[A-Za-z]:\\Users\\[^\\\r\n]+"),
    re.compile(r"[A-Za-z]:\\[^\r\n]*KG-MNP-Demo"),
    re.compile(r"AppData\\Local\\Programs\\Python"),
    re.compile(r"/home/[^/\r\n]+/[^ \r\n]*KG-MNP-Demo"),
    re.compile(r"/Users/[^/\r\n]+/[^ \r\n]*KG-MNP-Demo"),
]

MAX_TEXT_BYTES = 2 * 1024 * 1024

FORBIDDEN_TRACKED_PREFIXES = (
    "runtime_logs/",
    "runtime_data/",
    "runtime_outputs/",
    "runtime_reports/",
    "docs/ontology-site/",
    "build/",
    "dist/",
    "graphdb-data/",
    "graphdb-local/",
    "third_party/bin/",
    "third_party/downloads/",
)


def _git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    raw = result.stdout.split(b"\0")
    paths = [
        item.decode("utf-8", errors="surrogateescape")
        for item in raw
        if item
    ]
    # During an uncommitted cleanup, Git still lists paths deleted from the
    # working tree. Validate the repository that would remain, not tombstones.
    return [path for path in paths if (ROOT / path).is_file()]


def _segments(path: str) -> list[str]:
    return [part for part in path.replace("\\", "/").split("/") if part]


def _matches_forbidden_path(path: str) -> bool:
    parts = _segments(path)
    if not parts:
        return False

    for index, part in enumerate(parts):
        if part == ".venv" or part.startswith(".venv"):
            return True
        if part == "venv" or part.startswith("venv"):
            return True
        if part == "site-packages":
            return True
        if part == "pyvenv.cfg":
            return True
        if (
            part.lower() == "python.exe"
            and index > 0
            and parts[index - 1] == "Scripts"
        ):
            return True
        if (
            part.lower() == "pip.exe"
            and index > 0
            and parts[index - 1] == "Scripts"
        ):
            return True
        if (
            part == "site-packages"
            and index > 0
            and parts[index - 1] == "Lib"
        ):
            return True
    return False


def _is_excluded_from_abs_scan(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith((".git/", "runtime_reports/"))


def _looks_like_utf8_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def check_tracked_paths(paths: list[str] | None = None) -> list[str]:
    tracked = paths if paths is not None else _git_ls_files()
    failures = [
        f"tracked virtual environment: {path}"
        for path in tracked
        if _matches_forbidden_path(path)
    ]
    for path in tracked:
        normalized = path.replace("\\", "/")
        if normalized.startswith(FORBIDDEN_TRACKED_PREFIXES):
            failures.append(f"tracked runtime/build artifact: {path}")
        if normalized.lower().endswith(".jar"):
            failures.append(f"tracked third-party JAR: {path}")
    return failures


def check_absolute_paths(
    paths: list[str] | None = None,
    *,
    root: Path | None = None,
) -> list[str]:
    tracked = paths if paths is not None else _git_ls_files()
    base = root if root is not None else ROOT
    failures: list[str] = []
    for path in tracked:
        if _is_excluded_from_abs_scan(path):
            continue
        file_path = base / path
        if not file_path.is_file():
            continue
        try:
            size = file_path.stat().st_size
        except OSError:
            continue
        if size > MAX_TEXT_BYTES:
            continue
        try:
            data = file_path.read_bytes()
        except OSError:
            continue
        if not _looks_like_utf8_text(data):
            continue
        text = data.decode("utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in ABS_PATH_PATTERNS):
                failures.append(f"local absolute path in {path}:{line_no}")
                break
    return failures


def run_checks(
    paths: list[str] | None = None,
    *,
    root: Path | None = None,
) -> list[str]:
    return check_tracked_paths(paths) + check_absolute_paths(paths, root=root)


def main() -> int:
    failures = run_checks()
    if failures:
        print("Repository hygiene check failed:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("Repository hygiene check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
