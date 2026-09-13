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
    "demo_outputs/",
    "runtime/",
    "runtime_logs/",
    "runtime_data/",
    "runtime_outputs/",
    "runtime_reports/",
    "docs/ontology-site/",
    "build/",
    "dist/",
    "graphdb-data/",
    "graphdb-local/",
    ".graphdb/",
    "graphdb-logs/",
    "third_party/bin/",
    "third_party/downloads/",
    "workspace/",
    "workspaces/",
    ".kg-mnp/",
    ".kgmnp/",
    "local_artifacts/",
    "local_reports/",
)

FORBIDDEN_TOP_LEVEL_AUTHORITY_PREFIXES = (
    "ontology/",
    "data/",
    "inputs/",
    "mappings/",
    "rules/",
    "shapes/",
    "competency_questions/",
    "queries/",
)

FORBIDDEN_TOP_LEVEL_HISTORY_PREFIXES = (
    "legacy/",
    "archive/",
    "deprecated/",
    "old/",
)

SENSITIVE_FILE_NAMES = {".env", "id_rsa", "id_ed25519"}
SENSITIVE_SUFFIXES = (".license", ".pem", ".key", ".p12", ".pfx")
SECRET_CONTENT_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
    re.compile(r"\bagt_codex_[A-Za-z0-9_-]{20,}\b"),
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
        if part == "__pycache__" or part == ".pytest_cache":
            return True
        if part.endswith((".pyc", ".pyo")):
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
        if normalized.startswith(FORBIDDEN_TOP_LEVEL_AUTHORITY_PREFIXES):
            failures.append(f"top-level domain authority duplicate: {path}")
        if normalized.startswith(FORBIDDEN_TOP_LEVEL_HISTORY_PREFIXES):
            failures.append(f"forbidden history directory: {path}")
        old_namespace_prefix = "src/kg_" + "mnp_demo/"
        if normalized.startswith(old_namespace_prefix):
            failures.append(f"old Python package namespace: {path}")
        file_name = Path(normalized).name.lower()
        if file_name in SENSITIVE_FILE_NAMES or file_name.startswith(".env."):
            failures.append(f"tracked sensitive environment/key file: {path}")
        if file_name.endswith(SENSITIVE_SUFFIXES):
            failures.append(f"tracked sensitive license/key file: {path}")
        if normalized.lower().endswith(".jar"):
            failures.append(f"tracked third-party JAR: {path}")
        if normalized.lower().endswith(".license"):
            failures.append(f"tracked GraphDB license: {path}")
    return failures


def check_sensitive_content(
    paths: list[str] | None = None,
    *,
    root: Path | None = None,
) -> list[str]:
    """Detect high-confidence private keys and common live-token formats."""

    tracked = paths if paths is not None else _git_ls_files()
    base = root if root is not None else ROOT
    failures: list[str] = []
    for path in tracked:
        file_path = base / path
        if not file_path.is_file():
            continue
        try:
            data = file_path.read_bytes()
        except OSError:
            continue
        if len(data) > MAX_TEXT_BYTES or not _looks_like_utf8_text(data):
            continue
        text = data.decode("utf-8")
        if any(pattern.search(text) for pattern in SECRET_CONTENT_PATTERNS):
            failures.append(f"high-confidence secret/private key content: {path}")
    return failures


def check_golden_locations(paths: list[str] | None = None) -> list[str]:
    """Require reviewed expected/golden fixture trees to use allowed roots."""

    tracked = paths if paths is not None else _git_ls_files()
    failures: list[str] = []
    for path in tracked:
        normalized = path.replace("\\", "/")
        parts = _segments(normalized)
        has_golden_marker = any(
            part in {"fixtures", "golden", "goldens", "expected"}
            or part.startswith("expected-")
            for part in parts
        )
        if not has_golden_marker:
            continue
        allowed = (
            normalized.startswith(("tests/", "examples/")) or normalized.startswith("domain_packs/") and "/fixtures/" in normalized
        )
        if not allowed:
            failures.append(f"golden fixture outside allowed roots: {path}")
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
    return (
        check_tracked_paths(paths)
        + check_absolute_paths(paths, root=root)
        + check_sensitive_content(paths, root=root)
        + check_golden_locations(paths)
    )


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
